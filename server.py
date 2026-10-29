"""Dependency-free, local-first reverse engineering research workspace."""
import io, ipaddress, json, os, re, socket, sqlite3, uuid, zipfile
import threading
from engine.investigation import investigate
from engine.synthesis import validate_design, local_design
from pathlib import Path
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
MUTATION_LOCK = threading.Lock()
ROOT = Path(__file__).parent
DB = Path(os.environ.get('RES_DATA_DIR', str(ROOT / '.data'))) / 'projects.db'
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
    return conn

def save(p):
    with connect() as c: c.execute('INSERT OR REPLACE INTO projects VALUES (?,?)', (p['id'], json.dumps(p)))
def get(key):
    with connect() as c: row = c.execute('SELECT body FROM projects WHERE id=?', (key,)).fetchone()
    if not row: raise ValueError('Project not found')
    return json.loads(row[0])
def validate_url(url):
    p = urlparse(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.port not in (None,80,443):
        raise ValueError('Use a public HTTP(S) URL on a standard port, without credentials.')
    addresses = socket.getaddrinfo(p.hostname, p.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Local, private, and reserved addresses are not supported.')
class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)
class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.title=[]; self.headings=[]; self.description=''; self.capture=None
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag in ('title','h1','h2','h3'): self.capture=tag
        if tag=='meta' and attrs.get('name','').lower()=='description': self.description=attrs.get('content','')[:1000]
    def handle_endtag(self, tag):
        if tag==self.capture: self.capture=None
    def handle_data(self, data):
        value=' '.join(data.split())[:300]
        if value and self.capture=='title': self.title.append(value)
        elif value and self.capture: self.headings.append(value)
def inspect(url):
    validate_url(url)
    with build_opener(Redirects()).open(Request(url,headers={'User-Agent':'ReverseEngineeringWorkspace/0.1'}),timeout=15) as r:
        if 'text/html' not in r.headers.get('Content-Type',''): raise ValueError('Reference must return HTML.')
        data=r.read(1_000_001)
        if len(data)>1_000_000: raise ValueError('Reference exceeds the 1 MB research limit.')
        parser=Parser(); parser.feed(data.decode(r.headers.get_content_charset() or 'utf-8',errors='replace'))
        return {'url':r.url,'title':' '.join(parser.title),'description':parser.description,'headings':parser.headings[:30],
                'limitations':'Static HTML only. JavaScript content, login flows, backend logic, and actual feature behavior have not been inspected.'}
def plan(p):
    evidence=p.get('evidence')
    return {'mode':'Rule-based planning · no AI model used','goal':p['goal'],
        'observations': ([{'claim':'Page title: '+evidence['title'],'source':evidence['url']}]+[{'claim':'Visible heading: '+h,'source':evidence['url']} for h in evidence['headings'][:10]]) if evidence else [],
        'features':[{'name':line.strip(' -•\t'),'source':'User requirement','acceptance':'Verify the complete workflow, including successful, empty, and error states.'} for line in p['requirements'].splitlines() if line.strip(' -•\t')],
        'assumptions':['Reference internals remain unknown.','Single-user local deployment is the initial target.','External API and content access need separate validation.'],
        'questions':['What data must persist?','Which features are essential for the first release?','Which services provide authorized access to the required data?'],
        'milestones':['Review specification and external access dependencies.','Design screens and persistent data model.','Implement one complete user workflow.','Add approved features with functional tests.','Validate deployment, costs, and recovery.'],
        'cost':'This workspace uses no paid APIs. Future integrations may incur separate costs.'}
def export(p):
    output=io.BytesIO(); spec=p.get('plan') or plan(p)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('project.json',json.dumps(p,indent=2))
        if p.get('investigation',{}).get('analysis'):
            run=p['investigation']
            z.writestr('research/investigation.json',json.dumps(run,indent=2))
            z.writestr('research/ARCHITECTURE_PROMPT.txt',run['handoff']['prompt'])
            z.writestr('research/REQUIREMENTS.md','# Evidence matrix\n\n'+'\n'.join(
                '- '+r['id']+' ['+r['status']+'] '+r['requirement']+' — '+', '.join(r['evidence_ids']) for r in run['analysis']['matrix']))
        if p.get('design'):
            z.writestr('research/PROPOSED_DESIGN.json',json.dumps(p['design'],indent=2))
        z.writestr('SPECIFICATION.md','# '+p['name']+'\n\n'+p['goal']+'\n\n## Requested features\n\n'+'\n'.join('- '+f['name'] for f in spec['features'])+'\n\n## Milestones\n\n'+'\n'.join('- '+m for m in spec['milestones'])+'\n\n## Open questions\n\n'+'\n'.join('- '+q for q in spec['questions'])+'\n\nPlanning export only: application code has not been generated or verified.\n')
    return output.getvalue()
class Handler(BaseHTTPRequestHandler):
    def reply(self,status,data,kind='application/json'):
        data=json.dumps(data).encode() if kind=='application/json' else data
        self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(data)))
        self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'")
        self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/api/projects':
            with connect() as c: projects=[json.loads(r[0]) for r in c.execute('SELECT body FROM projects ORDER BY rowid DESC')]
            return self.reply(200,projects)
        if re.fullmatch(r'/api/projects/[a-f0-9]+/export',path):
            try: return self.reply(200,export(get(path.split('/')[3])),'application/zip')
            except ValueError as e: return self.reply(404,{'error':str(e)})
        files={'/':('index.html','text/html'),'/app.js':('app.js','text/javascript'),'/style.css':('style.css','text/css')}
        if path in files:
            name,kind=files[path]; return self.reply(200,(ROOT/'web'/name).read_bytes(),kind)
        self.reply(404,{'error':'Not found'})
    def do_POST(self):
        if not MUTATION_LOCK.acquire(blocking=False):
            return self.reply(409,{'error':'Another operation is running. Please retry when it finishes.'})
        try:
            self.handle_post()
        finally:
            MUTATION_LOCK.release()
    def handle_post(self):
        if self.headers.get('Origin') and self.headers['Origin']!='http://'+self.headers.get('Host',''):
            return self.reply(403,{'error':'Cross-origin requests are not permitted'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=65536: raise ValueError('Request must be between 1 byte and 64 KB.')
            body=json.loads(self.rfile.read(size)); path=urlparse(self.path).path
            if not isinstance(body,dict): raise ValueError('Expected a JSON object.')
            if path=='/api/projects':
                for field in ('name','goal','requirements'):
                    if not isinstance(body.get(field),str) or not body[field].strip(): raise ValueError(field+' is required')
                p={k:body[k].strip() for k in ('name','goal','requirements')}
                p.update(id=uuid.uuid4().hex,reference=str(body.get('reference','')).strip(),stage='Discover')
            elif re.fullmatch(r'/api/projects/[a-f0-9]+/(inspect|plan|investigate|design)',path):
                p=get(path.split('/')[3])
                if path.endswith('/investigate'):
                    if not isinstance(body.get('refresh',False),bool): raise ValueError('refresh must be true or false')
                    p=investigate(p,body.get('repositories'),save,refresh=body.get('refresh',False))
                elif path.endswith('/design'):
                    run=p.get('investigation')
                    if not run or not run.get('profiles'): raise ValueError('Investigate a repository successfully before proposing a design.')
                    if body.get('provider')=='ollama':
                        value=local_design(run['handoff']['prompt']); provider='ollama'
                    elif body.get('provider')=='handoff':
                        value=body.get('response'); provider='handoff (user-supplied)'
                    else: raise ValueError('Select ollama or handoff.')
                    p['design']=validate_design(value,run['analysis'],run['profiles'])
                    p['design'].update(provider=provider,prompt_sha256=run['handoff']['sha256'])
                elif path.endswith('/inspect'): p['evidence']=inspect(p['reference']); p.pop('plan',None); p['stage']='Specify'
                else: p['plan']=plan(p); p['stage']='Review'
            else: return self.reply(404,{'error':'Not found'})
            save(p); self.reply(200,p)
        except (ValueError,OSError,TypeError) as e: self.reply(400,{'error':str(e)})
if __name__=='__main__':
    connect().close(); port=int(os.environ.get('PORT','8000'))
    print(f'Workspace listening on http://127.0.0.1:{port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
