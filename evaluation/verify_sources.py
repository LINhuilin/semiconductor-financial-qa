"""Verify official CNINFO full reports against local page text; retain version differences."""
import concurrent.futures,urllib.request,urllib.parse,json,hashlib, pathlib,re,datetime
import fitz
ROOT=pathlib.Path(__file__).resolve().parents[1]
def compact(t):return re.sub(r'\s+','',t)
def verify(item):
 name=item['company']
 data=urllib.parse.urlencode(dict(pageNum=1,pageSize=30,column='szse',tabName='fulltext',searchkey=name+' 2025年年度报告',seDate='2026-01-01~2026-10-13',sortName='time',sortType='desc')).encode()
 try:
  req=urllib.request.Request('https://www.cninfo.com.cn/new/hisAnnouncement/query',data=data,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=40) as r:obj=json.load(r)
  entries=[x for x in (obj.get('announcements') or []) if '2025年年度报告' in x['announcementTitle'] and not any(s in x['announcementTitle'] for s in ['摘要','提示','英文','审计','更正公告'])]
  local=fitz.open(ROOT/'reports'/item['file']); best=None; versions=[]
  for x in entries:
   url='https://static.cninfo.com.cn/'+x['adjunctUrl']
   with urllib.request.urlopen(url,timeout=60) as r:b=r.read()
   official=fitz.open(stream=b,filetype='pdf')
   matched=sum(compact(local[i].get_text(sort=True))==compact(official[i].get_text(sort=True)) for i in range(min(len(local),len(official))))
   record=dict(url=url,title=x['announcementTitle'],announcement_id=x['announcementId'],official_pages=len(official),matched_pages=matched,local_pages=len(local),official_sha256=hashlib.sha256(b).hexdigest(),byte_identical=hashlib.sha256(b).hexdigest()==item['sha256'],all_page_text_identical=len(local)==len(official)==matched)
   versions.append(record)
   if best is None or matched>best['matched_pages']:best=record
  item.update(official_versions=versions,verified_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
  if best:
   item.pop('verification_error',None)
   item.update(official_url=best['url'],official_title=best['title'],source_verified=best['all_page_text_identical'],verification=best)
  else:item.update(source_verified=False,verification_error='未找到年度报告全文')
 except Exception as e:item.update(source_verified=False,verification_error=str(e))
 print(name,item.get('source_verified'),flush=True);return item
if __name__=='__main__':
 items=json.loads((ROOT/'data/inventory.json').read_text())
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:result=list(pool.map(verify,items))
 (ROOT/'data/inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 (ROOT/'evaluation/revision/official_sources.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
