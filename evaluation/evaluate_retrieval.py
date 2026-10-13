"""Separate retrieval coverage from answer correctness; original + controlled paraphrases (dictionary-assisted; not held-out)."""
import csv,json,sys,pathlib,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine import Engine
refs=json.loads((ROOT/'evaluation/reference_answers.json').read_text())
variants={
'1':'兆易创新2025年的营收规模和同比增幅各是多少？',
'2':'北京君正2025年归属上市公司股东赚了多少钱？',
'3':'澜起科技2025年经营现金净流入有多少？',
'4':'瑞芯微2025年研发花费多少，占营收的比重是多少？',
'5':'全志科技2025年主营芯片有哪些种类？',
'6':'中芯国际2025年销售额多少，金额币种和数量单位是什么？',
'7':'华虹公司2025年披露的经营隐患有哪些？',
'8':'长电科技、通富微电、华天科技2025年销售额由高到低排列，金额换成人民币亿元。',
'9':'兆易创新、澜起科技、北京君正、瑞芯微、全志科技2025年收入增长速度哪家最快？请逐家列数。',
'10':'兆易创新2027年将有多少营收？只依据2025年报能确定吗？'}
def main():
 e=Engine();rows=list(csv.DictReader((ROOT/'evaluation/questions.csv').open(encoding='utf-8-sig')));results=[]
 for row in rows:
  names=row['选择公司'].split('、');target=refs[row['题号']]['reference_pages']
  for label,q in [('original',row['问题']),('paraphrase',variants[row['题号']])]:
   for route,rules in [('lsa',False),('bm25',False),('hybrid',False),('hybrid',True)]:
    hits=e.search(q,names,k=max(12,3*len(names)),route=route,use_rules=rules)
    for c in names:
     pages={h['page'] for h in hits if h['company']==c};gold=set(target.get(c,[]))
     results.append(dict(question_id=row['题号'],variant=label,question=q,company=c,route=route,rules=rules,k=max(12,3*len(names)),gold_pages=sorted(gold),retrieved_pages=sorted(pages),page_recall=len(gold&pages)/len(gold) if gold else None,all_gold_pages_recalled=gold<=pages if gold else None,chunk_ids=[h['id'] for h in hits if h['company']==c],answer_evaluated=False))
 out=ROOT/'evaluation/revision';out.mkdir(exist_ok=True)
 (out/'retrieval_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
 summary=[]
 for route,rules in [('lsa',False),('bm25',False),('hybrid',False),('hybrid',True)]:
  for variant in ['original','paraphrase']:
   selected=[r for r in results if r['route']==route and r['rules']==rules and r['variant']==variant and r['page_recall'] is not None]
   summary.append(dict(route=route,rules=rules,variant=variant,company_question_pairs=len(selected),all_pages_hit=sum(r['all_gold_pages_recalled'] for r in selected),mean_page_recall=sum(r['page_recall'] for r in selected)/len(selected),failures=[{'id':r['question_id'],'company':r['company'],'missing_pages':sorted(set(r['gold_pages'])-set(r['retrieved_pages']))} for r in selected if not r['all_gold_pages_recalled']]))
 (out/'retrieval_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
