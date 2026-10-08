from pathlib import Path
import json,pickle,argparse
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer,CountVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
ROOT=Path(__file__).resolve().parent
# 中文字符二元组避免依赖分词词典，英文/数字保留完整 token。
from tokenizer import tokenize
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--model',default=''); a=ap.parse_args()
 records=json.loads((ROOT/'data/chunks.json').read_text(encoding='utf-8'))
 texts=[r['company']+' '+r['section']+' '+r['text'] for r in records]
 counts=CountVectorizer(tokenizer=tokenize,token_pattern=None,min_df=1)
 matrix=counts.fit_transform(texts).astype(float).tocsr(); lengths=np.asarray(matrix.sum(axis=1)).ravel()
 df=np.asarray((matrix>0).sum(axis=0)).ravel(); idf=np.log(1+(len(records)-df+.5)/(df+.5))
 if a.model:
  from sentence_transformers import SentenceTransformer
  encoder=SentenceTransformer(a.model)
  vectors=encoder.encode(texts,batch_size=16,normalize_embeddings=True,show_progress_bar=True)
  state=dict(mode='neural',model=a.model)
 else:
  tf=TfidfVectorizer(tokenizer=tokenize,token_pattern=None,min_df=2,max_features=40000)
  x=tf.fit_transform(texts); svd=TruncatedSVD(n_components=min(128,x.shape[0]-1,x.shape[1]-1),random_state=42)
  vectors=normalize(svd.fit_transform(x)); state=dict(mode='lsa',tf=tf,svd=svd)
 state.update(counts=counts,matrix=matrix,lengths=lengths,idf=idf,vectors=np.asarray(vectors,dtype=np.float32))
 with (ROOT/'data/index.pkl').open('wb') as f:pickle.dump(state,f)
 print('索引完成：',state['mode'],len(records))
if __name__=='__main__': main()
