import json,threading,webbrowser,urllib.parse,os
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from engine import Engine,ROOT
engine=Engine(); lock=threading.Lock()
class Handler(BaseHTTPRequestHandler):
 def send(self,data,kind='application/json',status=200):
  b=data if isinstance(data,bytes) else data.encode('utf-8');self.send_response(status);self.send_header('Content-Type',kind if kind=='application/pdf' else kind+'; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path=='/':self.send((ROOT/'page.html').read_bytes(),'text/html')
  elif self.path=='/inventory':self.send((ROOT/'data/inventory.json').read_bytes())
  elif self.path.startswith('/reports/'):
   name=urllib.parse.unquote(urllib.parse.urlsplit(self.path).path[len('/reports/'):])
   if '/' in name or '\\' in name or not name.endswith('.pdf'):
    self.send('不存在','text/plain',404);return
   path=ROOT/'reports'/name
   if not path.is_file():self.send('不存在','text/plain',404);return
   self.send(path.read_bytes(),'application/pdf')
  else:self.send('不存在','text/plain',404)
 def do_POST(self):
  if self.path!='/ask':self.send('{}',status=404);return
  try:
   data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
   q=str(data.get('question','')).strip()[:2000]; names=data.get('companies') or None
   if not q:raise ValueError('请输入问题')
   if names is not None and (not isinstance(names,list) or any(n not in engine.companies for n in names)):
    raise ValueError('请选择清单中的公司')
   with lock:
    hits=engine.search(q,names,k=max(12,3*len(engine.selected_companies(q,names))));response=engine.respond(q,hits,names)
   for h in hits:h['pdf_url']='/reports/'+urllib.parse.quote(h['file'])+'#page='+str(h['page'])
   result=dict(question=q,hits=hits,index_mode=engine.s['mode'],**response)
   with (ROOT/'evaluation/runs.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(result,ensure_ascii=False)+'\n')
   self.send(json.dumps(result,ensure_ascii=False))
  except (ValueError,KeyError,TypeError) as e:self.send(json.dumps({'error':str(e)},ensure_ascii=False),status=400)
  except Exception as e:self.send(json.dumps({'error':str(e)},ensure_ascii=False),status=500)
 def log_message(self,*args):pass
if __name__=='__main__':
 print('浏览器打开 http://127.0.0.1:8501 ，关闭程序按 Ctrl+C')
 if os.environ.get('QA_NO_BROWSER')!='1':webbrowser.open('http://127.0.0.1:8501')
 ThreadingHTTPServer(('127.0.0.1',8501),Handler).serve_forever()
