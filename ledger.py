"""Metadata-only canonical totals: cloud client counters plus local scheduler events."""
import json,sqlite3,time,pathlib,contextlib,collections,math
COUNTERS=('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens','reasoning_tokens','calls')
TEXT=('id','machine','profile','session','parent','provider','model','role','scope','kind','status','measurement','request_id','gpu_name')
METRICS=('timestamp','duration_ms','images','gpu_seconds','gpu_temp_min','gpu_temp_max','gpu_temp_sum','gpu_temp_samples','timed_output_tokens','timed_duration_ms','timed_calls')
ALLOWED=set(COUNTERS+TEXT+METRICS+('baseline',))
# Optional alias -> [backend identifier, display name] JSON file.
import os
ALIAS_BACKEND = json.loads(pathlib.Path(os.environ['USAGE_MODEL_MAP']).read_text()) if os.environ.get('USAGE_MODEL_MAP') else {}

def validate(r):
 if not isinstance(r,dict) or set(r)-ALLOWED:raise ValueError('Only allowlisted usage metadata is accepted')
 for k in ('id','machine','model','scope','kind','timestamp'):
  if k not in r:raise ValueError('Missing '+k)
 for k in TEXT:
  if k in r and (not isinstance(r[k],str) or len(r[k])>256 or any(ord(x)<32 for x in r[k])):raise ValueError('Invalid '+k)
 for k in COUNTERS+METRICS:
  if k in r and r[k] is not None and (isinstance(r[k],bool) or not isinstance(r[k],(int,float)) or not math.isfinite(r[k]) or r[k]<0 or (k in COUNTERS and int(r[k])!=r[k])):raise ValueError('Invalid numeric '+k)
 if r['kind'] not in ('event','snapshot'):raise ValueError('Invalid kind')
 if r['scope'] not in ('cloud','local','local-observation','image'):raise ValueError('Invalid scope')
 return dict(r)
class Store:
 def __init__(self,path):
  self.path=str(path)
  with self.connect() as c:c.executescript('''PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,payload TEXT NOT NULL,updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS deltas(seq INTEGER PRIMARY KEY,record_id TEXT NOT NULL,payload TEXT NOT NULL,observed REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,last_seen REAL NOT NULL);
CREATE INDEX IF NOT EXISTS deltas_observed ON deltas(observed);''')
 @contextlib.contextmanager
 def connect(self):
  c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row
  try:
   with c:yield c
  finally:c.close()
 def ingest(self,records):
  if not isinstance(records,list) or len(records)>2000:raise ValueError('Expected at most 2000 records')
  rows=[validate(r) for r in records];now=time.time()
  with self.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   for r in rows:
    prior=c.execute('SELECT payload FROM records WHERE id=?',(r['id'],)).fetchone();old=json.loads(prior[0]) if prior else None
    c.execute('INSERT INTO sources VALUES(?,?) ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen',(r['machine'],now))
    if old and (r['timestamp']<old['timestamp'] or r==old):continue
    if old and r['kind']=='snapshot' and old.get('measurement')!=r.get('measurement'):
     c.execute('DELETE FROM deltas WHERE record_id=?',(r['id'],));old=None
    if old and r['kind']=='event':
     for k in COUNTERS:
      if old.get(k) is not None:r[k]=old[k]
    delta=dict(r)
    if old:
     reset=any(r.get(k) is not None and old.get(k) is not None and r[k]<old[k] for k in COUNTERS)
     for k in COUNTERS+('timed_output_tokens','timed_duration_ms','timed_calls'):delta[k]=None if reset or r.get(k) is None or old.get(k) is None else r[k]-old[k]
     delta['baseline']=False
    if not r.get('baseline',False) or old:
     if not old or any(delta.get(k) for k in COUNTERS):c.execute('INSERT INTO deltas(record_id,payload,observed) VALUES(?,?,?)',(r['id'],json.dumps(delta,sort_keys=True),now))
    c.execute('INSERT INTO records VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated',(r['id'],json.dumps(r,sort_keys=True),now))
  return len(rows)
 def summary(self,days=0):
  with self.connect() as c:
   if days:rows=[json.loads(r[0]) for r in c.execute('SELECT payload FROM deltas WHERE observed>=?',(time.time()-days*86400,))]
   else:rows=[json.loads(r[0]) for r in c.execute('SELECT payload FROM records')]
   sources=[dict(r) for r in c.execute('SELECT * FROM sources ORDER BY id')]
   observations=c.execute("SELECT count(*) FROM records WHERE json_extract(payload,'$.scope')='local-observation'").fetchone()[0]
  rows=[r for r in rows if r['scope'] in ('cloud','local','image')]
  def totals(rs):
   d={k:sum(r.get(k) or 0 for r in rs) for k in COUNTERS};d.update(records=len(rs),unknown_records=sum(r.get('input_tokens') is None or r.get('output_tokens') is None for r in rs if r['scope']!='image'),total_tokens=d['input_tokens']+d['output_tokens'],images=sum(r.get('images',0) for r in rs))
   timed=[(r.get('timed_output_tokens'),r.get('timed_duration_ms'),r.get('timed_calls',1)) if r.get('timed_duration_ms',0) else (r.get('output_tokens'),r.get('duration_ms'),1) for r in rs if r['scope'] in ('cloud','local') and (r.get('timed_duration_ms',0) or (r['kind']=='event' and r.get('duration_ms',0)))]
   timed=[(n,t,c) for n,t,c in timed if n is not None and t and t>0]
   elapsed=sum(t for n,t,c in timed);d['avg_tokens_per_second']=sum(n for n,t,c in timed)*1000/elapsed if elapsed else None;d['timed_records']=sum(c or 0 for n,t,c in timed)
   measured=[r for r in rs if r['scope'] in ('local','image') and r.get('gpu_temp_samples',0)>0]
   samples=sum(r['gpu_temp_samples'] for r in measured)
   d['gpu_name']='; '.join(sorted({r['gpu_name'] for r in rs if r['scope'] in ('local','image') and r.get('gpu_name')})) or None
   d['gpu_temp_min']=min((r['gpu_temp_min'] for r in measured if r.get('gpu_temp_min') is not None),default=None)
   d['gpu_temp_max']=max((r['gpu_temp_max'] for r in measured if r.get('gpu_temp_max') is not None),default=None)
   d['gpu_temp_avg']=sum(r.get('gpu_temp_sum',0) for r in measured)/samples if samples else None
   d['gpu_temp_samples']=samples
   return d
  groups=collections.defaultdict(list)
  for r in rows:groups[(r['machine'],r.get('provider',''),r['model'],r.get('role',''),r['scope'])].append(r)
  result=totals(rows);result['groups']=[dict(machine=k[0],provider=k[1],model=k[2],role=k[3],scope=k[4],**totals(v)) for k,v in sorted(groups.items())]
  for g in result['groups']:
    if g['model'] in ALIAS_BACKEND:
      backend_id,backend_name=ALIAS_BACKEND[g['model']]
      g['backend']=backend_name; g['backend_model']=backend_id
    else:
      g['backend']=g['model']; g['backend_model']=None
  result['sources']=sources;result['local_client_observations']=observations
  result['days']=days;result['generated_at']=time.time();result['coverage']='Cloud: retained Hermes accounting. Local: scheduled requests since instrumentation. Historical baselines excluded from time windows; deltas use receipt time, not exact request time. Local client observations are NOT added to scheduler totals. Direct backend calls and lost upstream usage are not guaranteed.'
  return result
