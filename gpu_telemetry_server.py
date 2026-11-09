"""Read-only NVIDIA telemetry restricted to loopback clients."""
import csv,subprocess,http.server,json,threading,time,pathlib
LOCK=threading.Lock();CACHE={'gpus':[],'sampled_at':None}
def query(fields,kind='gpu'):
 r=subprocess.run(['/usr/bin/nvidia-smi','--query-'+kind+'='+fields,'--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2,check=True)
 return list(csv.reader(r.stdout.splitlines(),skipinitialspace=True))
def collect():
 processes={}
 for row in query('gpu_uuid,process_name','compute-apps'):
  if len(row)<2:continue
  name=row[1].lower();kind='ollama' if 'ollama' in name else 'image' if 'python' in name or 'comfy' in name else 'other'
  processes.setdefault(row[0],set()).add(kind)
 gpus=[]
 for uuid,name,temp in query('uuid,name,temperature.gpu'):
  try:t=float(temp)
  except ValueError:continue
  kinds=sorted(processes.get(uuid,()))
  gpus.append({'uuid':uuid,'name':name,'temperature':t,'active':bool(kinds),'process_kinds':kinds})
 return {'gpus':gpus,'sampled_at':time.time()}
def loop():
 global CACHE
 while True:
  try:result=collect()
  except Exception:result={'gpus':[],'sampled_at':None}
  with LOCK:CACHE=result
  time.sleep(0.75)
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  if self.client_address[0] not in ('127.0.0.1','::1'):self.send_error(403);return
  if self.path!='/metrics':self.send_error(404);return
  with LOCK:raw=json.dumps(CACHE).encode()
  self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
if __name__=='__main__':
 threading.Thread(target=loop,daemon=True).start();http.server.ThreadingHTTPServer(('127.0.0.1',11438),Handler).serve_forever()
