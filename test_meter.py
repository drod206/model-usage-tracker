import unittest,pathlib,tempfile,os
class MeterTests(unittest.TestCase):
 def test_split_stream_usage_and_no_content_persistence(self):
  import usage_meter
  self.assertTrue(hasattr(usage_meter,'Meter'),'Usage stream parser not implemented')
  m=usage_meter.Meter('job','code','hermes-code:latest','127.0.0.1')
  m.feed(b'data: {"choices":[{"delta":{"content":"PRIVATE RESPONSE"}}]}\n\n');m.feed(b'data: {"usage":{"prompt_tokens":12,"completion_');m.feed(b'tokens":4,"prompt_tokens_details":{"cached_tokens":8}}}\n\ndata: [DONE]\n\n')
  r=m.result('complete');self.assertEqual(r['input_tokens'],12);self.assertEqual(r['output_tokens'],4);self.assertEqual(r['cache_read_tokens'],8);self.assertNotIn('PRIVATE',str(r))
 def test_native_final_and_missing_usage(self):
  import usage_meter
  self.assertTrue(hasattr(usage_meter,'Meter'),'Usage stream parser not implemented')
  m=usage_meter.Meter('j','vision','hermes-cua:latest','peer');m.feed(b'{"done":true,"prompt_eval_count":7,"eval_count":3}');r=m.result('complete');self.assertEqual(r['input_tokens'],7);self.assertEqual(r['output_tokens'],3)
  m=usage_meter.Meter('k','code','m','peer');self.assertIsNone(m.result('failed')['input_tokens'])
if __name__=='__main__':unittest.main()
