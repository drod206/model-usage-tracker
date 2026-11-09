import unittest,time
class GpuTests(unittest.TestCase):
 def test_only_active_allowed_devices_contribute(self):
  from gpu_monitor import GpuMonitor
  m=GpuMonitor(['GPU-one'])
  m.sample({'gpus':[{'uuid':'GPU-one','name':'V100','temperature':50,'active':True},{'uuid':'GPU-other','name':'2080','temperature':90,'active':True}]})
  m.sample({'gpus':[{'uuid':'GPU-one','name':'V100','temperature':60,'active':True}]})
  r=m.result();self.assertIn('V100',r['gpu_name']);self.assertEqual(r['gpu_temp_min'],50);self.assertEqual(r['gpu_temp_max'],60);self.assertEqual(r['gpu_temp_sum'],110);self.assertEqual(r['gpu_temp_samples'],2)
 def test_missing_and_idle_telemetry_remain_unknown(self):
  from gpu_monitor import GpuMonitor
  m=GpuMonitor(['GPU-one']);m.sample({'gpus':[{'uuid':'GPU-one','name':'V100','temperature':40,'active':False}]});self.assertEqual(m.result(),{})
 def test_monitor_failures_do_not_interrupt_usage(self):
  from gpu_monitor import GpuMonitor
  m=GpuMonitor(['GPU-one'],url='http://127.0.0.1:1');m.start();m.stop();self.assertEqual(m.result(),{})
if __name__=='__main__':unittest.main()
