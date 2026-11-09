import unittest
from unittest.mock import patch
from usage_meter import Meter
class MeterTimingTests(unittest.TestCase):
 def test_request_timing_excludes_queue_and_unload(self):
  m=Meter('job','vision','model','peer')
  with patch('usage_meter.time.monotonic',return_value=100):m.start_inference([])
  with patch('usage_meter.time.monotonic',return_value=102):m.stop_inference()
  m.feed(b'{"usage":{"prompt_tokens":10,"completion_tokens":20}}')
  self.assertEqual(m.result('complete')['duration_ms'],2000)
if __name__=='__main__':unittest.main()
