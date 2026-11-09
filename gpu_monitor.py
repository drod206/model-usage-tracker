"""Best-effort read-only GPU sampling, scoped to a held inference lease."""
import threading,json,urllib.request,math
class GpuMonitor:
 def __init__(self,uuids,url='http://127.0.0.1:11438/metrics',process_kind='ollama'):
  self.allowed=set(uuids);self.url=url;self.process_kind=process_kind;self.done=threading.Event();self.lock=threading.Lock();self.names=set();self.temps=[];self.thread=None
 def sample(self,payload):
  for g in payload.get('gpus',[]):
   t=g.get('temperature');kinds=g.get('process_kinds')
   if g.get('uuid') not in self.allowed or not g.get('active') or (kinds is not None and self.process_kind not in kinds):continue
   if isinstance(t,bool) or not isinstance(t,(float,int)) or not math.isfinite(t) or not 0<=t<=150:continue
   with self.lock:
    self.names.add(g['name']+' ['+g['uuid'].removeprefix('GPU-')[:8]+']');self.temps.append(t)
 def poll(self):
  while not self.done.is_set():
   try:
    with urllib.request.urlopen(self.url,timeout=1.5) as r:payload=json.load(r)
    self.sample(payload)
   except Exception:pass # no telemetry error may break inference
   self.done.wait(0.75)
 def start(self):
  if self.thread or not self.allowed:return
  self.thread=threading.Thread(target=self.poll,daemon=True);self.thread.start()
 def stop(self):
  self.done.set()
  if self.thread:self.thread.join(timeout=0.1)
 def result(self):
  with self.lock:
   if not self.temps:return {}
   return {'gpu_name':'; '.join(sorted(self.names)),'gpu_temp_min':min(self.temps),'gpu_temp_max':max(self.temps),'gpu_temp_sum':sum(self.temps),'gpu_temp_samples':len(self.temps)}
