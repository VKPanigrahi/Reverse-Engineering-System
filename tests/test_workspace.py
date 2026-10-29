import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile
import server

class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.old_db=server.DB
        server.DB=Path(cls.temp.name)/'test.db'
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.http.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join();server.DB=cls.old_db;cls.temp.cleanup()
    def request(self,path,body=None,headers=None):
        req=Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers or {})
        return urlopen(req)
    def test_full_project_workflow_and_persistence(self):
        with self.request('/api/projects',{'name':'Music','goal':'Listen to my collection','requirements':'Upload songs\nEdit playlists','reference':'https://example.com'}) as r: p=json.load(r)
        evidence={'url':'https://example.com','title':'Music reference','description':'Library','headings':['Playlists'],'limitations':'Static HTML only'}
        with patch('server.inspect',return_value=evidence):
            with self.request('/api/projects/'+p['id']+'/inspect',{}) as r: self.assertEqual(json.load(r)['stage'],'Specify')
        with self.request('/api/projects/'+p['id']+'/plan',{}) as r: p=json.load(r)
        self.assertEqual(len(p['plan']['features']),2)
        self.assertEqual(p['plan']['observations'][1]['claim'],'Visible heading: Playlists')
        self.assertEqual(server.get(p['id']),p)
        with self.request('/api/projects') as r: self.assertIn(p,json.load(r))
        with self.request('/api/projects/'+p['id']+'/export') as r:
            with zipfile.ZipFile(io.BytesIO(r.read())) as z:
                self.assertIn('Edit playlists',z.read('SPECIFICATION.md').decode())
                self.assertEqual(json.loads(z.read('project.json'))['id'],p['id'])
    def test_investigation_design_and_research_export(self):
        from test_investigation import fixture
        with self.request('/api/projects',{'name':'Research','goal':'Music','requirements':'Upload songs'}) as r: p=json.load(r)
        base='/api/projects/'+p['id']
        with patch('engine.investigation.acquire',return_value=fixture()):
            with self.request(base+'/investigate',{'repositories':['example/music']}) as r: p=json.load(r)
        self.assertEqual(p['investigation']['status'],'completed')
        self.assertEqual(p['investigation']['analysis']['matrix'][0]['status'],'candidate-source')
        ref=p['investigation']['profiles'][0]['records'][0]['id']
        proposal={'summary':'Local uploads','findings':[{'requirement_id':'R1','approach':'Persist a local library','evidence_ids':[ref],'unknowns':['Size limit']} ]}
        with self.request(base+'/design',{'provider':'handoff','response':proposal}) as r: p=json.load(r)
        self.assertIn('user-supplied',p['design']['provider'])
        proposal['findings'][0]['evidence_ids']=['fake']
        with self.assertRaises(HTTPError) as ctx: self.request(base+'/design',{'provider':'handoff','response':proposal})
        self.assertEqual(ctx.exception.code,400)
        self.assertEqual(server.get(p['id'])['design']['findings'][0]['evidence_ids'],[ref])
        with self.request(base+'/export') as r:
            with zipfile.ZipFile(io.BytesIO(r.read())) as z:
                self.assertIn('research/ARCHITECTURE_PROMPT.txt',z.namelist())
                self.assertIn('research/PROPOSED_DESIGN.json',z.namelist())
        p['investigation']={'status':'running','profiles':[]};server.save(p)
        with self.request(base+'/export') as r: self.assertEqual(r.status,200)

    def test_page_parser(self):
        p=server.Parser();p.feed('<title>Music</title><meta name="description" content="Listen"><h1>My library</h1><script>private()</script>')
        self.assertEqual(p.title,['Music']);self.assertEqual(p.headings,['My library']);self.assertEqual(p.description,'Listen')
    def test_private_and_redirect_targets_rejected(self):
        for url in ['file:///etc/passwd','http://127.0.0.1','http://[::1]','http://169.254.169.254','https://user:pass@example.com','https://example.com:8080']:
            with self.subTest(url=url),self.assertRaises(ValueError): server.validate_url(url)
        with self.assertRaises(ValueError): server.Redirects().redirect_request(None,None,302,'',{},'http://127.0.0.1/')
    def test_invalid_and_cross_origin_requests(self):
        with self.assertRaises(HTTPError) as ctx: self.request('/api/projects',{})
        self.assertEqual(ctx.exception.code,400)
        with self.assertRaises(HTTPError) as ctx: self.request('/api/projects',{}, {'Origin':'https://elsewhere.example'})
        self.assertEqual(ctx.exception.code,403)
    def test_ui_and_static_routes(self):
        with self.request('/') as r: self.assertIn(b'What do you want to build?',r.read())
        with self.assertRaises(HTTPError) as ctx: self.request('/server.py')
        self.assertEqual(ctx.exception.code,404)

if __name__=='__main__': unittest.main()
