import tempfile,time,unittest
from pathlib import Path
from ledger import Store

class LastUsedTests(unittest.TestCase):
 def test_latest_usage_timestamp_not_ingest_time(self):
  with tempfile.TemporaryDirectory() as d:
   store=Store(Path(d)/'usage.sqlite')
   self.assertIsNone(store.summary().get('last_used'))
   for ident,ts in [('new',1700000200),('old',1700000000)]:
    store.ingest([dict(id=ident,machine='example',model='example-model',scope='local',kind='event',timestamp=ts,input_tokens=1,output_tokens=1,calls=1)])
   for days in (0,1):
    result=store.summary(days)
    self.assertEqual(result.get('last_used'),1700000200)
    self.assertEqual(result['groups'][0].get('last_used'),1700000200)

if __name__=='__main__':unittest.main()
