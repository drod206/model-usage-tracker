"""Bounded in-memory parsing; only usage metadata is written to the durable outbox."""
import json,time,pathlib,os,logging
class Meter:
 def __init__(self,identity,route,model,peer):
  self.identity=identity;self.route=route;self.model=model;self.peer=peer;self.started=time.time();self.buffer=b'';self.usage={};self.monitor=None;self.inference_started=None;self.inference_duration=None;self.telemetry={}
 def start_inference(self,uuids):
  self.inference_started=time.monotonic()
  try:
   from gpu_monitor import GpuMonitor
   self.monitor=GpuMonitor(uuids);self.monitor.start()
  except Exception:pass
 def stop_inference(self):
  if self.inference_started is not None and self.inference_duration is None:self.inference_duration=(time.monotonic()-self.inference_started)*1000
  if self.monitor:
   self.monitor.stop();self.telemetry=self.monitor.result()
 def parse(self,raw):
  try:
   if raw.startswith(b'data:'):raw=raw[5:].strip()
   d=json.loads(raw)
   if not isinstance(d,dict):return
   if isinstance(d.get('usage'),dict) and d['usage']:self.usage=d['usage']
   if 'prompt_eval_count' in d or 'eval_count' in d:self.usage={'prompt_tokens':d.get('prompt_eval_count'),'completion_tokens':d.get('eval_count'),'prompt_tokens_details':{'cached_tokens':d.get('prompt_eval_cached_count')}}
  except (ValueError,TypeError):pass
 def feed(self,block):
  self.buffer+=block
  while b'\n' in self.buffer:
   line,self.buffer=self.buffer.split(b'\n',1);self.parse(line.strip())
  if len(self.buffer)>2097152:self.buffer=b''
 def result(self,status):
  self.parse(self.buffer.strip());u=self.usage
  def num(x):return x if isinstance(x,int) and not isinstance(x,bool) and x>=0 else None
  r=dict(id='scheduler:'+self.identity,request_id=self.identity,machine='local-scheduler',profile='',session='',parent='',provider='ollama',model=self.model,role=self.route,scope='local',kind='event',timestamp=self.started,baseline=False,input_tokens=num(u.get('prompt_tokens')),output_tokens=num(u.get('completion_tokens')),cache_read_tokens=num((u.get('prompt_tokens_details') or {}).get('cached_tokens')),reasoning_tokens=num((u.get('completion_tokens_details') or {}).get('reasoning_tokens')),calls=1,status=status,measurement='provider-reported' if u else 'unavailable',duration_ms=round(self.inference_duration if self.inference_duration is not None else (time.time()-self.started)*1000,3))
  r.update(self.telemetry);return r
 def save(self,status,root='./state/usage-outbox'):
  try:
   p=pathlib.Path(root);p.mkdir(exist_ok=True);f=p/(self.identity+'.json');t=f.with_suffix('.tmp');t.write_text(json.dumps(self.result(status)));t.replace(f)
  except Exception:logging.exception('Usage accounting failed; inference continues')
