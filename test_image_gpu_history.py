import unittest
class HistoricalImageGpuTests(unittest.TestCase):
 def test_runtime_readback_backfills_identity_but_never_temperature(self):
  from usage_agent import image_gpu_metadata
  j={'unload_readback':{'devices':[{'name':'cuda:0 NVIDIA GeForce RTX 2080 Ti : cudaMallocAsync','type':'cuda','index':0}]}}
  r=image_gpu_metadata(j);self.assertIn('RTX 2080 Ti',r['gpu_name']);self.assertIn('runtime readback',r['gpu_name']);self.assertNotIn('gpu_temp_min',r);self.assertNotIn('gpu_temp_samples',r)
 def test_sampled_metadata_takes_precedence_and_is_allowlisted(self):
  from usage_agent import image_gpu_metadata
  r=image_gpu_metadata({'gpu_telemetry':{'gpu_name':'Tesla V100 [uuid]','gpu_temp_min':42,'gpu_temp_max':43,'gpu_temp_sum':85,'gpu_temp_samples':2,'prompt':'never persist'}})
  self.assertEqual(r['gpu_name'],'Tesla V100 [uuid]');self.assertNotIn('prompt',r)
 def test_absent_and_cpu_only_history_remain_unrecorded(self):
  from usage_agent import image_gpu_metadata
  self.assertEqual(image_gpu_metadata({}),{});self.assertEqual(image_gpu_metadata({'unload_readback':{'devices':[{'name':'cpu','type':'cpu'}]}}),{})
if __name__=='__main__':unittest.main()
