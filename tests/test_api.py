import unittest, tempfile, threading, json, urllib.request, urllib.error, time, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

class PortalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        server.DB=str(Path(cls.temp.name)/'test.db')
        server.ADMIN_KEY='test-key-not-for-production-123456789'
        server.init_db()
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.url='http://127.0.0.1:'+str(cls.http.server_port)
        threading.Thread(target=cls.http.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.temp.cleanup()
    def call(self,path,data=None,token=None):
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        req=urllib.request.Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urllib.request.urlopen(req) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def create(self):
        status,result=self.call('/api/admin/requests',{'supplier':'Teste','items':[{'id':'x','order':'45001','item':'10','material':'A','description':'Peça','quantity':2}]},server.ADMIN_KEY)
        self.assertEqual(status,201)
        return result,result['url'].split('#token=')[1]
    def test_admin_requires_auth(self):
        self.assertEqual(self.call('/api/admin/requests',{})[0],401)
    def test_token_and_no_leak(self):
        request,token=self.create()
        self.assertEqual(self.call('/api/request',token='wrong')[0],404)
        code,data=self.call('/api/request',token=token)
        self.assertEqual(code,200);self.assertNotIn('token_hash',data)
        self.assertEqual(self.call('/api/admin/requests/'+request['id'],token=token)[0],401)
    def test_expired(self):
        request,token=self.create()
        with server.connect() as db:db.execute('UPDATE requests SET expires=? WHERE id=?',(int(time.time())-1,request['id']))
        self.assertEqual(self.call('/api/request',token=token)[0],410)
        self.assertEqual(self.call('/api/draft',{'answers':{}},token)[0],410)
    def test_draft_submit_and_duplicate(self):
        request,token=self.create()
        self.assertEqual(self.call('/api/draft',{'answers':{'x':{'received':'Sim'}},'responder':'Ana'},token)[0],200)
        self.assertEqual(self.call('/api/request',token=token)[1]['answers']['x']['received'],'Sim')
        answer={'answers':{'x':{'received':'Sim','shipped':'Não','divergence':'Não'}},'responder':'Ana'}
        self.assertEqual(self.call('/api/submit',answer,token)[0],200)
        self.assertEqual(self.call('/api/submit',answer,token)[0],409)
        self.assertEqual(self.call('/api/draft',answer,token)[0],409)
        result=self.call('/api/admin/requests/'+request['id'],token=server.ADMIN_KEY)[1]
        self.assertEqual(result['status'],'submitted');self.assertEqual(result['responder'],'Ana')
    def test_foreign_item_rejected(self):
        _,token=self.create()
        self.assertEqual(self.call('/api/draft',{'answers':{'other':{}}},token)[0],400)
    def test_required_fields(self):
        _,token=self.create()
        self.assertEqual(self.call('/api/submit',{'answers':{},'responder':'Ana'},token)[0],400)
        answer={'answers':{'x':{'received':'Sim','shipped':'Não','divergence':'Sim'}},'responder':'Ana'}
        self.assertEqual(self.call('/api/submit',answer,token)[0],400)
    def test_invalid_date(self):
        _,token=self.create()
        self.assertEqual(self.call('/api/draft',{'answers':{'x':{'forecast':'2026-02-30'}}},token)[0],400)
    def test_separate_tokens(self):
        first,token_a=self.create();second,token_b=self.create()
        self.call('/api/draft',{'answers':{'x':{'invoice':'123'}}},token_a)
        self.assertEqual(self.call('/api/request',token=token_b)[1]['answers'],{})
        self.assertNotEqual(first['id'],second['id'])
    def test_static_headers(self):
        with urllib.request.urlopen(self.url) as r:
            self.assertEqual(r.status,200)
            self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy'])
            self.assertIn('Portal do fornecedor',r.read().decode())

if __name__=='__main__':unittest.main()
