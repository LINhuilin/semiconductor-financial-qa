"""Actual HTTP /ask tests: evidence recall, answer correctness, citations separated."""
import pathlib,sys,subprocess,json,csv,time,urllib.request,hashlib
import fitz
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'evaluation'))
from evaluation_checks import check_response
from evaluate_retrieval import variants

def main():
 out=ROOT/'evaluation/revision'
 rows=list(csv.DictReader((ROOT/'evaluation/questions.csv').open(encoding='utf-8-sig')))
 refs=json.loads((ROOT/'evaluation/reference_answers.json').read_text());chunks={x['id']:x for x in json.loads((ROOT/'data/chunks.json').read_text())}
 pdfs={p.name:fitz.open(p) for p in (ROOT/'reports').glob('*.pdf')}
 code="import app,urllib.request; exec('def forbid(*a,**k):\\n raise RuntimeError(\"No API permitted\")'); urllib.request.urlopen=forbid; s=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler); print(s.server_address[1],flush=True); s.serve_forever()"
 proc=subprocess.Popen([sys.executable,'-u','-c',code],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 results=[];responses=[];csvrows=[]
 try:
  port=proc.stdout.readline().strip();assert port.isdigit(),proc.stderr.read();url='http://127.0.0.1:'+port
  for row in rows:
   for variant,q in [('original',row['问题']),('paraphrase',variants[row['题号']])]:
    t=time.monotonic();names=row['选择公司'].split('、')
    req=urllib.request.Request(url+'/ask',data=json.dumps({'question':q,'companies':names}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req) as r:result=json.load(r)
    errors,citations=check_response(row,result,refs,chunks,pdfs)
    company_evaluation=[]
    for company in names:
     gold=set(refs[row['题号']]['reference_pages'].get(company,[]));pages={h['page'] for h in result['hits'] if h['company']==company}
     fs=[f for f in result['facts'] if f['company']==company]
     company_evaluation.append({'company':company,'gold_pages':sorted(gold),'retrieved_pages':sorted(pages),'recall':len(gold&pages)/len(gold) if gold else None,'answer_fact_count':len(fs),'quotes_supported':all(c['quote_in_actual_pdf'] for c in citations if c['company']==company) if fs else None})
    entry={'id':row['题号'],'variant':variant,'question':q,'answer_correct':not errors,'errors':errors,'citations':citations,'company_evaluation':company_evaluation,'elapsed_seconds':round(time.monotonic()-t,3),'answer_status':result['answer_status']}
    results.append(entry);responses.append(dict(id=row['题号'],variant=variant,**result))
    csvrows.append({'题号':row['题号'],'版本':variant,'问题':q,'标准答案':refs[row['题号']]['reference_answer'],'召回':json.dumps(company_evaluation,ensure_ascii=False),'回答':result['answer'],'回答正确性':not errors,'引用正确性':all(c['quote_in_actual_pdf'] for c in citations) if citations else '无事实引用','错误原因':'；'.join(errors),'方式':'实际HTTP接口；非浏览器点击'})
    print(row['题号'],variant,not errors,errors,flush=True)
  (out/'http_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
  (out/'http_responses.jsonl').write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in responses)+'\n')
  with (out/'10题与改写评价.csv').open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(csvrows[0]));w.writeheader();w.writerows(csvrows)
 finally:
  proc.terminate();proc.wait(timeout=10)
if __name__=='__main__':main()
