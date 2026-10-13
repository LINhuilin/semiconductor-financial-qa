"""Portable built corpus; index.pkl is always rebuilt on the target machine."""
from pathlib import Path
import gzip,json,sqlite3,hashlib
ROOT=Path(__file__).resolve().parent

def load_records():
 p=ROOT/'data/chunks.json'
 if p.exists():return json.loads(p.read_text(encoding='utf-8'))
 with gzip.open(ROOT/'data/chunks.json.gz','rt',encoding='utf-8') as f:return json.load(f)

def save_portable(records):
 data=ROOT/'data';data.mkdir(exist_ok=True)
 with gzip.open(data/'chunks.json.gz','wt',encoding='utf-8') as f:json.dump(records,f,ensure_ascii=False)
 db=data/'knowledge_base.sqlite'
 if db.exists():db.unlink()
 with sqlite3.connect(db) as c:
  c.execute('CREATE TABLE chunks (chunk_id TEXT PRIMARY KEY, company TEXT, report_year TEXT, filename TEXT, pdf_page INTEGER, section TEXT, kind TEXT, content TEXT)')
  c.executemany('INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?)',[(r['id'],r['company'],r['year'],r['file'],r['page'],r['section'],r['kind'],r['text']) for r in records])
  c.execute('CREATE INDEX company_page ON chunks(company,pdf_page)')
 with db.open('rb') as src,gzip.open(data/'knowledge_base.sqlite.gz','wb') as dest:
  import shutil;shutil.copyfileobj(src,dest)
 db.unlink()
 return {'chunks':len(records),'companies':len({r['company'] for r in records}),'files':{n:hashlib.sha256((data/n).read_bytes()).hexdigest() for n in ['chunks.json.gz','knowledge_base.sqlite.gz']}}
