import pathlib,tempfile,unittest,os
import collector

class CollectorTests(unittest.TestCase):
 def setUp(self):
  self.assertTrue(hasattr(collector,'Store'),'Usage store not implemented')
  self.tmp=tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')); self.store=collector.Store(pathlib.Path(self.tmp.name)/'usage.sqlite')
 def tearDown(self): self.tmp.cleanup()
 def sample(self,**kw):
  d=dict(id='r1',machine='pc',profile='default',session='s',parent='',provider='openai-codex',model='gpt',role='coordinator',scope='cloud',kind='snapshot',input_tokens=10,output_tokens=3,cache_read_tokens=7,reasoning_tokens=2,calls=1,status='complete',measurement='provider-reported',timestamp=100,baseline=True)
  return dict(d,**kw)
 def test_idempotent_snapshot_and_cache_subset(self):
  self.store.ingest([self.sample()]); self.store.ingest([self.sample()]); s=self.store.summary(); self.assertEqual(s['input_tokens'],10); self.assertEqual(s['output_tokens'],3); self.assertEqual(s['total_tokens'],13); self.assertEqual(s['records'],1)

 def test_rejects_prompt_bodies_atomically(self):
  with self.assertRaises(ValueError):self.store.ingest([self.sample(),self.sample(id='bad',prompt='private')])
  self.assertEqual(self.store.summary()['records'],0)
 def test_unknown_usage_is_not_zero(self):
  self.store.ingest([self.sample(input_tokens=None,output_tokens=None)])
  self.assertEqual(self.store.summary()['unknown_records'],1)
 def test_canonical_scopes_prevent_double_counting(self):
  self.store.ingest([self.sample(),self.sample(id='service',scope='local',kind='event'),self.sample(id='clientlocal',scope='local-observation')])
  self.assertEqual(self.store.summary()['total_tokens'],26)
 def test_snapshot_delta_and_initial_baseline(self):
  self.store.ingest([self.sample()]); self.assertEqual(self.store.summary(days=1)['total_tokens'],0)
  self.store.ingest([self.sample(input_tokens=15,output_tokens=5,calls=2)])
  self.store.ingest([self.sample(input_tokens=15,output_tokens=5,calls=2)])
  self.assertEqual(self.store.summary(days=1)['total_tokens'],7)
 def test_stale_snapshot_does_not_roll_back(self):
  self.store.ingest([self.sample(timestamp=200,input_tokens=20)]);self.store.ingest([self.sample(timestamp=100)])
  self.assertEqual(self.store.summary()['input_tokens'],20)
 def test_independent_attempts_are_counted(self):
  self.store.ingest([self.sample(id='a',kind='event',scope='local',baseline=False),self.sample(id='b',kind='event',scope='local',baseline=False,status='failed')])
  self.assertEqual(self.store.summary()['total_tokens'],26)

 def test_http_requires_ingestion_token_and_serves_real_totals(self):
  self.assertTrue(hasattr(collector,'make_server'),'Collector HTTP server not implemented')
  import urllib.request,urllib.error,json,threading
  server=collector.make_server(self.store,'127.0.0.1',0,'private-test-token');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url='http://127.0.0.1:'+str(server.server_address[1])
  try:
   req=urllib.request.Request(url+'/api/ingest',data=json.dumps([self.sample()]).encode(),headers={'Content-Type':'application/json'})
   with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(req)
   self.assertEqual(cm.exception.code,401);cm.exception.close()
   req.add_header('Authorization','Bearer private-test-token')
   with urllib.request.urlopen(req) as r:self.assertEqual(r.status,200)
   with urllib.request.urlopen(url+'/api/summary') as r:self.assertEqual(json.load(r)['total_tokens'],13)
   with urllib.request.urlopen(url+'/') as r:self.assertIn(b'Model Usage',r.read())
  finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
