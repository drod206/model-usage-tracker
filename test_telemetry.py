import unittest,tempfile,pathlib,os
from ledger import Store,validate

class TelemetryTests(unittest.TestCase):
 def test_group_uses_weighted_measured_rates_and_temperatures(self):
  with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as d:
   s=Store(pathlib.Path(d)/'usage.sqlite')
   base=dict(machine='scheduler',model='local',scope='local',kind='event',timestamp=100,input_tokens=10,calls=1)
   s.ingest([dict(base,id='a',output_tokens=100,duration_ms=2000,gpu_name='V100',gpu_temp_min=40,gpu_temp_max=60,gpu_temp_sum=150,gpu_temp_samples=3),dict(base,id='b',output_tokens=300,duration_ms=3000,gpu_name='V100',gpu_temp_min=50,gpu_temp_max=70,gpu_temp_sum=130,gpu_temp_samples=2)])
   g=s.summary()['groups'][0]
   self.assertEqual(g['gpu_name'],'V100');self.assertEqual(g['gpu_temp_min'],40);self.assertEqual(g['gpu_temp_max'],70);self.assertEqual(g['gpu_temp_avg'],56);self.assertEqual(g['avg_tokens_per_second'],80);self.assertEqual(g['timed_records'],2)
 def test_old_cloud_rows_have_unknown_telemetry(self):
  with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as d:
   s=Store(pathlib.Path(d)/'usage.sqlite');s.ingest([dict(id='x',machine='pc',model='cloud',scope='cloud',kind='snapshot',timestamp=100,input_tokens=10,output_tokens=3,calls=1)])
   g=s.summary()['groups'][0]
   self.assertIsNone(g['gpu_name']);self.assertIsNone(g['gpu_temp_avg']);self.assertIsNone(g['avg_tokens_per_second'])
 def test_native_records_remain_valid_and_all_rows_are_returned(self):
  from test_agent import AgentTests
  AgentTests('test_reads_only_accounting_metadata_and_classifies_local').run(unittest.TestResult())
  import usage_agent,sqlite3
  with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as d:
   p=pathlib.Path(d);c=sqlite3.connect(p/'state.db');c.executescript('CREATE TABLE sessions(id TEXT,parent_session_id TEXT); CREATE TABLE session_model_usage(session_id TEXT, model TEXT,billing_provider TEXT,last_seen REAL); INSERT INTO sessions VALUES ("s",NULL); INSERT INTO session_model_usage VALUES ("s","one","cloud",100); INSERT INTO session_model_usage VALUES ("s","two","cloud",100);');c.close()
   rows=usage_agent.native_records(p,'pc',0);self.assertEqual(len(rows),2)
   for r in rows:validate(r);self.assertNotIn('gpu_temperature',r)

if __name__=='__main__':unittest.main()
