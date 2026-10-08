from pathlib import Path
import json,re,hashlib,sys
import fitz
ROOT=Path(__file__).resolve().parent
COMPANIES=['北京君正','长电科技','兆易创新','澜起科技','中芯国际','华虹公司','华天科技','全志科技','瑞芯微','通富微电']
def chunks(text,limit=650):
 lines=text.splitlines(); out=[]; current=''
 for line in lines:
  if len(current)+len(line)>limit and current:
   out.append(current); current=''
  current+=line+'\n'
 if current.strip(): out.append(current)
 return out

def main():
 result=[]; inventory=[]; errors=[]
 for path in sorted((ROOT/'reports').glob('*.pdf')):
  company=next((x for x in COMPANIES if x in path.name),path.stem)
  with fitz.open(path) as doc:
   cover=doc[0].get_text(); match=re.search(r'(20\d{2})\s*年年度报告',cover)
   year=match.group(1) if match else '未知'
   section='封面及前置信息'; table_count=0; short_pages=[]
   for pi,page in enumerate(doc):
    text=page.get_text(sort=True)
    if len(text.strip())<40: short_pages.append(pi+1)
    for line in text.splitlines():
     s=line.strip()
     if re.match(r'^第[一二三四五六七八九十百\d]+节\s*\S+',s) and len(s)<65 and not re.search(r'\.{3}|…|\s\d+$',s): section=s
    base=dict(company=company,year=year,file=path.name,page=pi+1,section=section)
    for ci,part in enumerate(chunks(text)):
     result.append(dict(base,id=f'{company}-p{pi+1}-t{ci}',kind='text',text=part))
    try:
     for ti,table in enumerate(page.find_tables().tables):
      rows=table.extract()
      if len(rows)<2: continue
      clean=lambda x: re.sub(r'\s+',' ',x or '').strip()
      head=' | '.join(clean(x) for x in rows[0]); context='\n'.join(text.splitlines()[:8])+ '\n本页单位提示（须确认适用于此表）：'+ '；'.join(x.strip() for x in text.splitlines() if '单位' in x or '币种' in x)
      for ri,row in enumerate(rows[1:],1):
       result.append(dict(base,id=f'{company}-p{pi+1}-table{ti}-r{ri}',kind='table_row',text=f'页面上部信息（单位可能在原页其他位置，须核对）：\n{context}\n表头：{head}\n第{ri}行：'+ ' | '.join(clean(x) for x in row)))
      table_count+=1
    except Exception as e: errors.append(dict(file=path.name,page=pi+1,error=str(e)))
   inventory.append(dict(company=company,year=year,file=path.name,pages=len(doc),tables=table_count,short_pages=short_pages,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),official_url='待补充官方公告链接'))
  print(company,year,'完成',flush=True)
 (ROOT/'data'/'chunks.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
 (ROOT/'data'/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
 (ROOT/'data'/'extraction_errors.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2),encoding='utf-8')
 print('分块数',len(result),'请运行 python index.py')
if __name__=='__main__':main()
