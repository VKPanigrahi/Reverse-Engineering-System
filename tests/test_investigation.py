import io
import json
import tarfile
import unittest
from unittest.mock import patch
from engine.repositories import analyze_files, read_archive, repository_name
from engine.synthesis import synthesize, handoff, validate_design, local_design
from engine.investigation import investigate

FILES = {'package.json':json.dumps({'name':'music','license':'MIT','dependencies':{'sqlite':'1'},'scripts':{'test':'node --test'}}),
         'src/library.py':'import sqlite3\ndef upload_song(path):\n    return path\n',
         'src/player.mjs':"import { readFile } from 'node:fs/promises';\nexport function playMusic() {}\n",
         'tests/test_library.py':'def test_upload_song():\n    assert True\n',
         'README.md':'# Music library\n## Offline playback\n',
         'Cargo.toml':'[package]\nname="music"\nlicense="MIT"\n[dependencies]\nchrono="1"'}

def fixture(name='example/music'):
    return analyze_files(name,'a'*40,FILES)

def archive(members):
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w:gz') as tar:
        for name,value in members.items():
            info=tarfile.TarInfo(name)
            if value is None: info.type=tarfile.SYMTYPE;info.linkname='/etc/passwd';tar.addfile(info)
            else: data=value.encode();info.size=len(data);tar.addfile(info,io.BytesIO(data))
    return output.getvalue()

class InvestigationTests(unittest.TestCase):
    def test_intake_rejects_other_hosts_credentials_and_options(self):
        self.assertEqual(repository_name('https://github.com/example/music.git'),'example/music')
        for value in ['https://gitlab.com/a/b','https://user:pass@github.com/a/b','--upload-pack=bad','../thing','https://github.com/a/b/tree/main']:
            with self.subTest(value=value),self.assertRaises(ValueError):repository_name(value)
    def test_archive_never_extracts_symlinks_secrets_or_dependencies(self):
        files,skipped=read_archive(archive({'repo/src/app.py':'print(1)','repo/.env':'secret','repo/node_modules/pkg/a.js':'bad','repo/link.py':None}))
        self.assertEqual(files,{'src/app.py':'print(1)'})
        self.assertEqual(skipped,2)
    def test_archive_rejects_traversal(self):
        with self.assertRaises(ValueError):read_archive(archive({'repo/../../app.py':'bad'}))
    def test_archive_sampling_reports_truncation(self):
        with patch('engine.repositories.MAX_FILES',1):
            files,skipped=read_archive(archive({'repo/one.py':'1','repo/two.py':'2'}))
        self.assertEqual(len(files),1);self.assertEqual(skipped,1)
    def test_profile_has_pinned_evidence_dependencies_and_imports(self):
        p=fixture()
        self.assertEqual(p['license'],'MIT');self.assertEqual(p['dependencies'],['chrono','sqlite'])
        symbol=next(r for r in p['records'] if r['text']=='upload_song')
        self.assertEqual(symbol['line'],2);self.assertIn('/'+'a'*40+'/',symbol['url'])
        module=next(m for m in p['modules'] if m['path']=='src/library.py')
        self.assertEqual(module['imports'],['sqlite3'])
        self.assertTrue(any(r['kind']=='test-symbol' for r in p['records']))
    def test_evidence_ids_are_stable_and_commit_sensitive(self):
        self.assertEqual(fixture(),fixture())
        self.assertNotEqual(fixture()['records'][0]['id'],analyze_files('example/music','b'*40,FILES)['records'][0]['id'])
    def test_synthesis_distinguishes_source_docs_and_gaps(self):
        analysis=synthesize('Upload songs\nOffline playback\nQuantum teleportation',[fixture()])
        self.assertEqual([r['status'] for r in analysis['matrix']],['candidate-source','documentation-only','gap'])
        self.assertEqual(analysis['summary']['verified_features'],0)
    def test_failed_reference_is_retained_and_retry_reuses_success(self):
        p={'goal':'Music','requirements':'Upload songs'};saved=[]
        with patch('engine.investigation.acquire',side_effect=[fixture(),ValueError('not available')]) as fetch:
            investigate(p,['example/music','example/missing'],lambda p:saved.append(json.loads(json.dumps(p))))
        self.assertEqual(p['investigation']['status'],'partial');self.assertGreaterEqual(len(saved),4)
        with patch('engine.investigation.acquire',return_value=fixture('example/missing')) as fetch:
            investigate(p,['example/music','example/missing'],lambda p:None)
            fetch.assert_called_once_with('example/missing')
        self.assertEqual(p['investigation']['status'],'completed')
        with patch('engine.investigation.acquire',return_value=fixture()) as fetch:
            investigate(p,['example/music'],lambda p:None,refresh=True);fetch.assert_called_once()
    def test_all_failures_never_claim_completion(self):
        p={'goal':'Music','requirements':'Upload songs'}
        with patch('engine.investigation.acquire',side_effect=ValueError('offline')):
            investigate(p,['example/music'],lambda p:None)
        self.assertEqual(p['investigation']['status'],'failed')
        self.assertEqual(p['investigation']['analysis']['summary']['gaps'],1)
    def test_design_validates_coverage_and_evidence(self):
        p=fixture();analysis=synthesize('Upload songs',[p]);ref=p['records'][0]['id']
        value={'summary':'Independent music app','findings':[{'requirement_id':'R1','approach':'Store local uploads','evidence_ids':[ref],'unknowns':['File limits']} ]}
        self.assertEqual(validate_design(value,analysis,[p])['findings'][0]['requirement_id'],'R1')
        value['findings'][0]['evidence_ids']=['invented']
        with self.assertRaises(ValueError):validate_design(value,analysis,[p])
        value['findings']=[]
        with self.assertRaises(ValueError):validate_design(value,analysis,[p])
    def test_handoff_and_unconfigured_local_model(self):
        p=fixture();analysis=synthesize('Upload songs',[p]);prompt=handoff('Music',analysis,[p])
        self.assertIn('untrusted data',prompt['prompt']);self.assertEqual(len(prompt['sha256']),64)
        with patch.dict('os.environ',{'RES_OLLAMA_MODEL':''}),self.assertRaises(ValueError):local_design('test')
    def test_local_model_adapter_parses_structured_response(self):
        result={'summary':'Proposed','findings':[]}
        response=io.BytesIO(json.dumps({'message':{'content':json.dumps(result)}}).encode())
        with patch.dict('os.environ',{'RES_OLLAMA_MODEL':'test'}),patch('engine.synthesis.build_opener') as opener:
            opener.return_value.open.return_value=response
            self.assertEqual(local_design('data'),result)
