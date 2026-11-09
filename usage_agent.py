"""Independent metadata-only accounting reader and durable forwarder."""
import pathlib,sqlite3,json,time,hashlib,urllib.parse,urllib.request,ssl,ipaddress,contextlib,sys,os
@contextlib.contextmanager
def db(path,readonly=False):
 c=sqlite3.connect(pathlib.Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=3) if readonly else sqlite3.connect(path,timeout=5)
 c.row_factory=sqlite3.Row
 try:
  with c:yield c
 finally:c.close()
def identity(parts):return hashlib.sha256(json.dumps(parts,sort_keys=True).encode()).hexdigest()
def native_records(home,machine,started,timing_path=None):
 home=pathlib.Path(home);out=[]
 if not (home/'state.db').exists():return out
 with db(home/'state.db',True) as c:
  tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  if 'session_model_usage' not in tables:raise RuntimeError('Hermes version has no per-model usage table; upgrade/integration required')
  cols={r['name'] for r in c.execute('PRAGMA table_info(session_model_usage)')}
  wanted=['session_id','model','billing_provider','billing_base_url','billing_mode','task','api_call_count','input_tokens','output_tokens','cache_read_tokens','cache_write_tokens','reasoning_tokens','first_seen','last_seen']
  parents={r['id']:r['parent_session_id'] or '' for r in c.execute('SELECT id,parent_session_id FROM sessions')}
  rows=[dict(r) for r in c.execute('SELECT '+','.join(k for k in wanted if k in cols)+' FROM session_model_usage')]
 timings={}
 if timing_path is not None:
  try:
   from timing_reader import timing_totals
   timings=timing_totals(home,timing_path)
  except (OSError,sqlite3.Error):pass # optional timing cannot discard canonical token counts
 for row in rows:
  endpoint=urllib.parse.urlsplit(row.get('billing_base_url') or '').hostname or '';local=False
  try:local=ipaddress.ip_address(endpoint).is_private
  except ValueError:local=endpoint=='localhost'
  provider=row.get('billing_provider') or 'unknown';scope='local-observation' if local or provider=='ollama' else 'cloud'
  key=[machine,home.name]+[row.get(k,'') for k in wanted[:6]]
  r=dict(id='native:'+identity(key),machine=machine,profile='default',session=row['session_id'],parent=parents.get(row['session_id'],''),provider=provider,model=row['model'],role=row.get('task') or 'coordinator',scope=scope,kind='snapshot',timestamp=row.get('last_seen') or time.time(),baseline=(row.get('first_seen') or 0)<started,status='recorded',measurement='hermes-canonical-inclusive-v1',calls=row.get('api_call_count'))
  for k in ('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens','reasoning_tokens'):r[k]=row.get(k)
  # Cache counts are subsets after normalization. No invented timing or GPU readings.
  if r['input_tokens'] is not None:r['input_tokens']+=(row.get('cache_read_tokens') or 0)+(row.get('cache_write_tokens') or 0)
  # Main-loop timing lines have no auxiliary task tag: attach only to an unambiguous coordinator row.
  matches=[x for x in rows if (x['session_id'],x['model'],x.get('billing_provider'))==(row['session_id'],row['model'],provider) and (x.get('task') or 'coordinator')=='coordinator']
  timed=timings.get((row['session_id'],row['model'],provider))
  if scope=='cloud' and r['role']=='coordinator' and len(matches)==1 and timed:r.update(timed)
  out.append(r)
 return out

class Queue:
 def __init__(self,path):
  self.path=path
  with db(path) as c:c.execute('CREATE TABLE IF NOT EXISTS pending(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
 def enqueue(self,records):
  with db(self.path) as c:
   for r in records:c.execute('INSERT INTO pending VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(r['id'],json.dumps(r,sort_keys=True)))
 def count(self):
  with db(self.path) as c:return c.execute('SELECT count(*) FROM pending').fetchone()[0]
 def flush(self,config):
  try:
   ctx=ssl.create_default_context(cafile=config.get('ca'))
   for _ in range(6):
    with db(self.path) as c:batch=c.execute('SELECT id,payload FROM pending LIMIT 500').fetchall()
    if not batch:return True
    req=urllib.request.Request(config['url']+'/api/ingest',data=('['+','.join(r['payload'] for r in batch)+']').encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+config['token']})
    with urllib.request.urlopen(req,context=ctx,timeout=5) as response:receipt=json.load(response)
    if receipt.get('accepted')!=len(batch):return False
    with db(self.path) as c:c.executemany('DELETE FROM pending WHERE id=? AND payload=?',[(r['id'],r['payload']) for r in batch])
   return self.count()==0
  except (OSError,ValueError):return False

def image_gpu_metadata(j):
 fields=('gpu_name','gpu_temp_min','gpu_temp_max','gpu_temp_sum','gpu_temp_samples')
 sampled={k:v for k,v in (j.get('gpu_telemetry') or {}).items() if k in fields}
 if sampled.get('gpu_name'):return sampled
 names=sorted({d['name'].split(' : ')[0] for d in (j.get('unload_readback') or {}).get('devices',[]) if d.get('type')=='cuda' and isinstance(d.get('name'),str) and len(d['name'])<200 and all(ord(c)>=32 for c in d['name'])})
 return {'gpu_name':'; '.join(names)+' (runtime readback)'} if names else {}

def cycle(config,root):
 q=Queue(root/'outbox.sqlite');records=[];errors=[];acked_files=[]
 if config.get('home'):
  try:records.extend(native_records(config['home'],config['machine'],config['started'],timing_path=root/'timings.sqlite'))
  except Exception as e:errors.append(type(e).__name__+': native accounting unavailable')
 if config.get('scheduler_outbox'):
  for p in pathlib.Path(config['scheduler_outbox']).glob('*.json'):
   try:records.append(json.loads(p.read_text()));acked_files.append(p)
   except (OSError,ValueError):errors.append('Invalid scheduler metadata file')
 if config.get('images'):
  for p in pathlib.Path(config['images']).glob('*.json'):
   try:
    j=json.loads(p.read_text());terminal=j.get('state') in ('complete','failed')
    if not terminal:continue
    records.append(dict(id='image:'+j['id'],request_id=j['id'],machine='local-scheduler',profile='',session='',parent='',provider='local',model=j['model'],role='images',scope='image',kind='event',timestamp=j.get('finished',j['created']),baseline=j['created']<config['started'],input_tokens=None,output_tokens=None,calls=1,status=j['state'],measurement='job-metadata',images=1 if j['state']=='complete' else 0,duration_ms=max(0,(j.get('finished',j['created'])-j.get('started',j['created']))*1000)))
    records[-1].update(image_gpu_metadata(j))
   except (OSError,ValueError,KeyError):errors.append('Image metadata unavailable')
 q.enqueue(records);sent=q.flush(config)
 if sent:
  for p in acked_files:p.unlink(missing_ok=True)
 result={'time':time.time(),'source':config['machine'],'read_records':len(records),'pending':q.count(),'uploaded':sent,'errors':errors}
 (root/'status.json').write_text(json.dumps(result));return result

if __name__=='__main__':
 root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else __file__).resolve()
 if root.is_file():root=root.parent
 config=json.loads((root/'agent.json').read_text());result=cycle(config,root);print(json.dumps(result))
