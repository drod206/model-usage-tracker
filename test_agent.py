import unittest,tempfile,pathlib,sqlite3,os
class AgentTests(unittest.TestCase):
 def test_reads_only_accounting_metadata_and_classifies_local(self):
  import usage_agent
  self.assertTrue(hasattr(usage_agent,'native_records'),'Native accounting reader not implemented')
  with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as d:
   p=pathlib.Path(d);c=sqlite3.connect(p/'state.db');c.executescript('CREATE TABLE sessions(id TEXT,parent_session_id TEXT); CREATE TABLE session_model_usage(session_id TEXT,model TEXT,billing_provider TEXT,billing_base_url TEXT,billing_mode TEXT,task TEXT,api_call_count INTEGER,input_tokens INTEGER,output_tokens INTEGER,cache_read_tokens INTEGER,cache_write_tokens INTEGER,reasoning_tokens INTEGER,first_seen REAL,last_seen REAL);');c.execute('INSERT INTO sessions VALUES(?,?)',('s',None));c.execute('INSERT INTO session_model_usage VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('s','gpt','openai-codex','','subscription','',1,20,3,10,0,2,100,200));c.execute('INSERT INTO session_model_usage VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('s','local','custom','http://127.0.0.1:11440/v1','','vision',1,5,2,0,0,0,100,200));c.commit();c.close()
   r=usage_agent.native_records(p,'pc',300);self.assertEqual(len(r),2);self.assertEqual(r[0]['scope'],'cloud');self.assertEqual(r[1]['scope'],'local-observation');self.assertEqual(r[0]['input_tokens'],30);self.assertNotIn('billing_base_url',r[0]);self.assertTrue(r[0]['baseline'])
 def test_outage_keeps_durable_queue(self):
  import usage_agent
  self.assertTrue(hasattr(usage_agent,'Queue'),'Durable queue not implemented')
  with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as d:
   p=pathlib.Path(d)/'queue.sqlite';q=usage_agent.Queue(p);q.enqueue([{'id':'r','input_tokens':3}]);self.assertFalse(q.flush({'url':'https://127.0.0.1:1','token':'test','ca':None}));self.assertEqual(usage_agent.Queue(p).count(),1)

if __name__=='__main__':unittest.main()
