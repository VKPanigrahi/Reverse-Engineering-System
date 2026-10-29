"""Bounded static profiling. Donor code is data and is never installed or run."""
import ast
import hashlib
import io
import json
from pathlib import PurePosixPath
import re
import subprocess
import tarfile
import tomllib
from urllib.request import Request, urlopen

MAX_ARCHIVE = 20_000_000
MAX_FILES = 800
MAX_FILE = 150_000
MAX_TEXT = 3_000_000
SKIP = {'.git', 'node_modules', 'vendor', 'dist', 'build', '.venv', 'target', 'coverage'}
EXTENSIONS = {'.py', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.rs', '.md', '.json', '.toml'}

def repository_name(value):
    if not isinstance(value, str):
        raise ValueError('Repository must be a GitHub URL or owner/name.')
    value = value.strip().removeprefix('https://github.com/').removesuffix('/').removesuffix('.git')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise ValueError('Use https://github.com/owner/repository (no branches, credentials, or query).')
    return value


def read_archive(data):
    """No extraction: reject symlinks, traversal, secrets, and excessive expansion."""
    files = {}
    used = 0
    skipped = 0
    expanded = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for index, member in enumerate(archive):
            if index >= 20_000:
                raise ValueError('Archive has too many entries.')
            expanded += member.size
            if expanded > 40_000_000:
                raise ValueError("Repository expands beyond the 40 MB analysis limit.")
            parts = PurePosixPath(member.name).parts
            if '..' in parts or member.name.startswith('/'):
                raise ValueError('Archive contains an unsafe path.')
            if len(parts) < 2 or not member.isfile():
                continue
            path = PurePosixPath(*parts[1:])
            if any(p in SKIP or p.startswith('.') for p in path.parts):
                skipped += 1
                continue
            eligible = path.suffix.lower() in EXTENSIONS or path.name.upper().startswith(('LICENSE', 'COPYING'))
            if not eligible or member.size > MAX_FILE:
                skipped += 1
                continue
            if len(files) >= MAX_FILES or used + member.size > MAX_TEXT:
                skipped += 1
                continue
            stream = archive.extractfile(member)
            content = stream.read(MAX_FILE + 1)
            if b'\x00' in content:
                skipped += 1
                continue
            files[str(path)] = content.decode('utf-8', errors='replace')
            used += len(content)
    return files, skipped


def acquire(value):
    name = repository_name(value)
    try:
        result = subprocess.run(['git', '-c', 'credential.interactive=false', 'ls-remote',
                                 'https://github.com/' + name + '.git', 'HEAD'],
                                capture_output=True, text=True, timeout=25, check=True)
    except (subprocess.SubprocessError, OSError) as error:
        raise ValueError('Cannot resolve repository HEAD through GitHub. Check network access and repository visibility.') from error
    commit = result.stdout.split()[0] if result.stdout.split() else ''
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Repository did not return a valid commit.')
    request = Request(f'https://codeload.github.com/{name}/tar.gz/{commit}',
                      headers={'User-Agent': 'Reframe/0.2'})
    with urlopen(request, timeout=30) as response:
        data = response.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        raise ValueError('Repository archive exceeds 20 MB; choose a smaller reference.')
    try:
        files, skipped = read_archive(data)
    except (tarfile.TarError, EOFError) as error:
        raise ValueError('Invalid repository archive.') from error
    profile = analyze_files(name, commit, files)
    profile['scope'].update(skipped_files=skipped, archive_sha256=hashlib.sha256(data).hexdigest())
    return profile


def analyze_files(name, commit, files):
    records = []
    modules = []
    warnings = []
    dependencies = set()
    scripts = {}
    license_label = 'Unknown — review license before reuse'
    def record(path, line, kind, text):
        text = text[:500]
        identity = json.dumps([name, commit, path, line, kind, text], ensure_ascii=True)
        item = {'id': 'ev-' + hashlib.sha256(identity.encode()).hexdigest()[:24], 'repository': name,
                'path': path, 'line': line, 'kind': kind, 'text': text,
                'url': f'https://github.com/{name}/blob/{commit}/{path}#L{line}'}
        records.append(item)
        return item['id']
    for path, text in sorted(files.items()):
        suffix = PurePosixPath(path).suffix
        is_test = bool(re.search(r'(^|/)(tests?|__tests__)/|[._](test|spec)[._]|(^|/)test_', path))
        if PurePosixPath(path).name.upper().startswith(('LICENSE', 'COPYING')):
            record(path, 1, 'license-text', text[:500])
        if suffix == '.md':
            for n, line in enumerate(text.splitlines(), 1):
                if re.match(r'^#{1,3} ', line) and len(records) < 1200:
                    record(path, n, 'documentation-claim', line.lstrip('# ').strip())
            continue
        if PurePosixPath(path).name == 'package.json':
            try:
                package = json.loads(text)
                dependencies.update(package.get('dependencies', {}).keys())
                scripts[path] = package.get('scripts', {})
                if isinstance(package.get('license'), str): license_label = package['license']
                record(path, 1, 'manifest', json.dumps({k:package[k] for k in ('name','description','license') if k in package}))
            except (ValueError, AttributeError, TypeError): warnings.append('Invalid manifest: ' + path)
        elif PurePosixPath(path).name in ('Cargo.toml', 'pyproject.toml'):
            try:
                package = tomllib.loads(text)
                metadata = package.get('package', package.get('project', {}))
                dep = package.get('dependencies', metadata.get('dependencies', []))
                dependencies.update(dep.keys() if isinstance(dep,dict) else dep)
                if isinstance(metadata.get('license'),str): license_label = metadata['license']
                record(path, 1, 'manifest', json.dumps(metadata)[:500])
            except (ValueError, TypeError, AttributeError): warnings.append('Invalid manifest: ' + path)
        if suffix not in {'.py','.js','.mjs','.cjs','.ts','.tsx','.jsx','.rs'}:
            continue
        symbols = []
        imports = []
        if suffix == '.py':
            try:
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        symbols.append((node.lineno, node.name))
                    elif isinstance(node, ast.Import): imports.extend(a.name for a in node.names)
                    elif isinstance(node, ast.ImportFrom): imports.append(node.module or '')
            except SyntaxError: warnings.append('Python syntax not parsed: ' + path)
        else:
            for n, line in enumerate(text.splitlines(), 1):
                match = re.search(r'(?:export\s+)?(?:async\s+)?(?:function|class|fn|struct|enum)\s+(\w+)|(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\(', line)
                if match: symbols.append((n, match.group(1) or match.group(2)))
                imports.extend(re.findall(r'(?:from\s+|require\()[\'\"]([^\'\"]+)', line))
                rust = re.match(r'\s*use\s+([\w:]+)',line)
                if rust: imports.append(rust.group(1))
        refs = [record(path, n, 'test-symbol' if is_test else 'source-symbol', symbol) for n,symbol in symbols[:60]]
        modules.append({'path':path,'test':is_test,'symbols':[s for _,s in symbols[:60]],'imports':sorted(set(imports))[:50],'evidence_ids':refs})
    return {'repository':name,'commit':commit,'license':license_label,'dependencies':sorted(dependencies),
            'scripts':scripts,'modules':modules,'records':records,'warnings':warnings,
            'scope':{'files_analyzed':len(files),'static_only':True,'execution':'No donor code, install scripts, or tests executed.',
                     'parser':'Python AST; heuristic JavaScript/TypeScript/Rust symbol and import detection.'}}
