import unittest,tempfile,time
from pathlib import Path
from unittest.mock import patch
import ledger

class ModelLabelsTests(unittest.TestCase):
 def test_configured_labels_only_annotate_real_records(self):
  with tempfile.TemporaryDirectory() as d, patch.object(ledger,'ALIAS_BACKEND',{'example:latest':['vendor/example','Example Model']}):
   store=ledger.Store(Path(d)/'usage.sqlite')
   self.assertEqual(store.summary()['groups'],[])
   store.ingest([dict(id='example-request',machine='example-source',model='example:latest',scope='local',kind='event',timestamp=time.time(),input_tokens=4,output_tokens=2,calls=1)])
   groups=store.summary()['groups']
   self.assertEqual(len(groups),1)
   self.assertEqual(groups[0]['backend'],'Example Model')
   self.assertEqual(groups[0]['backend_model'],'vendor/example')

if __name__=='__main__':unittest.main()
