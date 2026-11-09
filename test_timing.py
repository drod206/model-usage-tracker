import unittest,tempfile,pathlib,os
from usage_agent import native_records

class TimingTests(unittest.TestCase):
 def test_timing_attaches_only_to_matching_canonical_row_without_counting_twice(self):
  import sqlite3
  with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as d:
   p=pathlib.Path(d);(p/'logs').mkdir();line='2026-11-08 12:00:00,100 INFO [s] agent.conversation_loop: API call #1: model=gpt provider=openai-codex in=100 out=20 total=120 latency=2.0s id=resp_1\n'
   (p/'logs/agent.log').write_text(line+line)
   c=sqlite3.connect(p/'state.db');c.executescript('CREATE TABLE sessions(id TEXT,parent_session_id TEXT); CREATE TABLE session_model_usage(session_id TEXT,model TEXT,billing_provider TEXT,task TEXT,input_tokens INTEGER,output_tokens INTEGER,last_seen REAL); INSERT INTO sessions VALUES ("s",NULL); INSERT INTO session_model_usage VALUES ("s","gpt","openai-codex","coordinator",100,20,100); INSERT INTO session_model_usage VALUES ("s","gpt","openai-codex","title_generation",10,2,100);');c.close()
   r=native_records(p,'pc',0,timing_path=p/'timings.sqlite');self.assertEqual(r[0]['timed_output_tokens'],20);self.assertEqual(r[0]['timed_duration_ms'],2000);self.assertEqual(r[0]['timed_calls'],1);self.assertNotIn('timed_calls',r[1]);self.assertEqual(r[0]['output_tokens'],20)
   (p/'logs/agent.log').write_text('');r=native_records(p,'pc',0,timing_path=p/'timings.sqlite');self.assertEqual(r[0]['timed_calls'],1)
 def test_timing_failure_never_discards_canonical_accounting(self):
  import sqlite3
  with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as d:
   p=pathlib.Path(d);c=sqlite3.connect(p/'state.db');c.executescript('CREATE TABLE sessions(id TEXT,parent_session_id TEXT); CREATE TABLE session_model_usage(session_id TEXT,model TEXT,billing_provider TEXT,last_seen REAL); INSERT INTO sessions VALUES ("s",NULL); INSERT INTO session_model_usage VALUES ("s","gpt","openai-codex",100);');c.close()
   r=native_records(p,'pc',0,timing_path=p/'missing'/'timings.sqlite');self.assertEqual(len(r),1);self.assertNotIn('timed_calls',r[0])
if __name__=='__main__':unittest.main()
