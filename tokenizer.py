import re
def tokenize(text):
 tokens=re.findall(r'[A-Za-z0-9]+(?:[.,][0-9]+)*',text.lower())
 for run in re.findall(r'[\u4e00-\u9fff]+',text):
  tokens.extend(run[i:i+2] for i in range(len(run)-1))
 return tokens or ['空']
