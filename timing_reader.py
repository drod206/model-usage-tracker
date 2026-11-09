"""Read only structured API timing lines; never persist log bodies."""
import re,sqlite3,pathlib,hashlib,contextlib
LINE=re.compile(r'^(\S+ \S+) INFO \[([^]]+)\].*?API call #(\d+): model=(\S+) provider=(\S+) in=(\d+) out=(\d+) total=(\d+) latency=([\d.]+)s')
RID=re.compile(r'\bid=(\S+)')
def timing_totals(home,path):
 home=pathlib.Path(home);out={}
 with contextlib.closing(sqlite3.connect(path,timeout=5)) as c:
  c.execute('CREATE TABLE IF NOT EXISTS samples(id TEXT PRIMARY KEY,session TEXT,model TEXT,provider TEXT,output INTEGER,duration_ms REAL)')
  c.execute('CREATE TABLE IF NOT EXISTS cursors(path TEXT PRIMARY KEY,signature TEXT,offset INTEGER)')
  for f in (home/'logs').glob('agent.log*'):
   if not f.is_file() or f.suffix in ('.gz','.zip'):continue
   try:
    with f.open('rb') as log:
     # A first-line digest detects rotation/replacement, even after inode reuse.
     signature=hashlib.sha256(log.readline()).hexdigest();log.seek(0)
     prior=c.execute('SELECT signature,offset FROM cursors WHERE path=?',(str(f),)).fetchone()
     if prior and prior[0]==signature and prior[1]<=f.stat().st_size:log.seek(prior[1])
     while True:
      start=log.tell();raw=log.readline()
      if not raw:break
      if not raw.endswith(b'\n'):log.seek(start);break
      line=raw.decode('utf-8',errors='replace');m=LINE.search(line)
      if not m:continue
      date,session,call,model,provider,inp,output,total,seconds=m.groups();duration=float(seconds)*1000
      if duration<=0:continue
      rid=RID.search(line);identity=(rid[1] if rid else date+'|'+call)+'|'+session+'|'+model+'|'+provider
      key=hashlib.sha256(identity.encode()).hexdigest()
      c.execute('INSERT OR IGNORE INTO samples VALUES(?,?,?,?,?,?)',(key,session,model,provider,int(output),duration))
     c.execute('INSERT INTO cursors VALUES(?,?,?) ON CONFLICT(path) DO UPDATE SET signature=excluded.signature,offset=excluded.offset',(str(f),signature,log.tell()))
   except OSError:continue
  c.commit()
  for session,model,provider,output,duration,calls in c.execute('SELECT session,model,provider,SUM(output),SUM(duration_ms),COUNT(*) FROM samples GROUP BY session,model,provider'):
   out[(session,model,provider)]={'timed_output_tokens':output,'timed_duration_ms':duration,'timed_calls':calls}
 return out
