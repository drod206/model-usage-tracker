from ledger import Store
import http.server,urllib.parse,json,hmac,pathlib,ssl,os

def make_server(store,host,port,token):
 class Handler(http.server.BaseHTTPRequestHandler):
  server_version='UsageCollector/1'
  def log_message(self,*args):pass
  def send(self,status,payload,ctype='application/json'):
   raw=json.dumps(payload,allow_nan=False).encode() if ctype=='application/json' else payload
   self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'");self.end_headers();self.wfile.write(raw)
  def do_GET(self):
   path=urllib.parse.urlsplit(self.path)
   if path.path=='/health':return self.send(200,{'status':'ok'})
   if path.path=='/api/summary':
    try:days=int(urllib.parse.parse_qs(path.query).get('days',['0'])[0]);assert days in (0,1,7,30)
    except (ValueError,AssertionError):return self.send(400,{'error':'Invalid window'})
    return self.send(200,store.summary(days))
   if path.path in ('/','/dashboard.js'):
    file=pathlib.Path(__file__).parent/('dashboard.html' if path.path=='/' else 'dashboard.js')
    return self.send(200,file.read_bytes(),'text/html; charset=utf-8' if path.path=='/' else 'text/javascript; charset=utf-8')
   self.send(404,{'error':'Not found'})
  def do_POST(self):
   if self.path!='/api/ingest':return self.send(404,{'error':'Not found'})
   if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):return self.send(401,{'error':'Ingest credential required'})
   try:
    n=int(self.headers.get('Content-Length','0'))
    if not 0<n<=2097152:return self.send(413,{'error':'Body limit 2 MiB'})
    rows=json.loads(self.rfile.read(n));count=store.ingest(rows)
   except (ValueError,TypeError,KeyError):return self.send(400,{'error':'Invalid metadata batch'})
   return self.send(200,{'accepted':count})
 server=http.server.ThreadingHTTPServer((host,port),Handler);server.daemon_threads=True;return server

if __name__=='__main__':
 root=pathlib.Path(os.environ.get('USAGE_STATE','./state'));root.mkdir(parents=True,exist_ok=True)
 server=make_server(Store(root/'usage.sqlite'),os.environ.get('USAGE_BIND','localhost'),int(os.environ.get('USAGE_PORT','8443')),(root/'ingest-token').read_text().strip())
 context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2;context.load_cert_chain(root/'server.crt',root/'server.key');server.socket=context.wrap_socket(server.socket,server_side=True)
 server.serve_forever()
