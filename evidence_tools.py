"""Read-only evidence tools; deterministic routing, no LLM agent claims."""
import fitz,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def read(hit):
 path=ROOT/'reports'/hit['file']
 if path.parent.resolve()!=(ROOT/'reports').resolve():raise ValueError('非法PDF路径')
 with fitz.open(path) as doc:
  original=doc[hit['page']-1].get_text(sort=True)
 compact=lambda s:re.sub(r'\s+','',s)
 # Page records are assembled from original text chunks, not generated summaries.
 if hit['kind']=='page_text' and compact(hit['text'])!=compact(original):
  raise ValueError('正文分块合并与原PDF不一致')
 return dict(hit,evidence_read=True,read_tool='read',read_pdf_page=hit['page'])

def coverage(engine,question,hits,companies,result):
 from extractive import question_kind
 kind=question_kind(question);rows=[]
 for c in companies:
  read_pages=sorted({h['page'] for h in hits if h['company']==c and h.get('evidence_read')})
  facts=[f for f in result['facts'] if f['company']==c]
  need=sorted({p['page'] for p in engine.pages if p['company']==c and p['year']==result['target_year'] and p.get('risk_section')}) if kind=='risk' else []
  missing=sorted(set(need)-set(read_pages))
  status='missing' if not facts else 'partial' if missing else 'covered'
  rows.append(dict(company=c,obligation='所问指标及口径' if kind!='risk' else '风险章节原页',status=status,read_pages=read_pages,required_risk_pages=need,missing_pages=missing,fact_count=len(facts)))
 return rows
