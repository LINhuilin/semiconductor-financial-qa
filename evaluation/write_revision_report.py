import json,csv,pathlib,hashlib,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1];out=ROOT/'evaluation/revision'
results=json.loads((out/'http_results.json').read_text());responses=[json.loads(l) for l in (out/'http_responses.jsonl').read_text().splitlines()]
summary=json.loads((out/'retrieval_summary.json').read_text());manifest=json.loads((out/'build_manifest.json').read_text());sources=json.loads((ROOT/'data/inventory.json').read_text())
rows=[];risk=[]
for result in results:
 if result['id'] in ('8','9'):
  for r in result['company_evaluation']:rows.append({'题号':result['id'],'版本':result['variant'],'公司':r['company'],'标准页':r['gold_pages'],'召回页':r['retrieved_pages'],'页召回率':r['recall'],'答案正确':result['answer_correct'],'引文在PDF中':r['quotes_supported'],'事实数':r['answer_fact_count'],'错误原因':'；'.join(result['errors'])})
for response in responses:
 if response['id']=='7' and response['variant']=='original':
  for f in response['facts']:
   item=next(x for x in results if x['id']=='7' and x['variant']=='original');risk.append({'公司':f['company'],'报告年度':f['year'],'PDF页序':f['page'],'文件':f['file'],'引文':f['quote'],'原文存在':next(c['quote_in_actual_pdf'] for c in item['citations'] if c['source']==f['source']),'引用编号':f['source']})
for name,table in [('跨公司逐家公司评价.csv',rows),('风险引文逐项核对.csv',risk)]:
 with (out/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
lsa=next(s for s in summary if s['route']=='lsa' and s['variant']=='paraphrase');n=sum(x['answer_correct'] for x in results)
report=f'''# 修改后的实验结论（2026-10-13）

本库含10家公司2025年报，共2086个PDF页、{manifest['chunks']}个分块。巨潮资讯10份官方全文与提交文件SHA256全部一致，华虹使用2026-05-15修订版。官方URL、公告版本、核验时间与哈希见来源清单。提交可移植的压缩JSON及SQLite库，索引在目标机器重建。

采用BM25、128维LSA与RRF融合，并以章节/表头约束和公开的同义词字典补充召回。LSA是统计向量基线，不能称为预训练语义嵌入。对同一题集拆开测试：纯LSA在原题15个公司-问题对中完整命中2个，在受控改写中仅命中{lsa['all_pages_hit']}个；改写平均标准页召回率为{lsa['mean_page_recall']:.2%}。纯BM25、无规则混合及规则补充的结果均单列，规则补充在原题/改写各15个有标准页的公司-问题对中完整命中15个。这不能作为LSA语义泛化通过的证据；改写字典是人工配置，也不是独立留出测试。

实际HTTP测试为10道原题及10道改写，{n}/20符合有限参考答案和引文检查；其中两道跨公司题各按公司记录召回页、答案及出处，召回正确与回答正确分别评价。华虹风险19条标题逐项核对PDF20-23页，保留完整原文编号；原页图、原文文本与核对表均可回查。修复了“2027年收入，依据2025年报”句式被误判目标年份的问题。

抽取式系统未调用大模型或付费API。数值换算使用Decimal，缺证、异币种或冲突不作完整排名；未知指标明确说明不足。固定题集通过不等于一般问答准确率，也不等于教师验收。已对照第三课61-63、90-92及163页，增加问题路由、原PDF阅读白名单、逐家公司证据覆盖表，以及风险缺页补查（最多40次原页阅读）。这是确定性规则流程，不宣称实现课件中的LLM Agent或GraphRAG。浏览器截图与界面测试结果另见web目录。
'''
(out/'一页结论.md').write_text(report)
lines=['# 批改意见与修改对应','', '| 老师意见 | 已修改 | 证据 |','|---|---|---|', '| 补建库 | 压缩JSON + SQLite库，保留公司/年度/章节/页码/分块ID/原文 | data/*.gz；build_manifest.json；build.log |','| 官方全文来源清单 | 10份官方全文URL与SHA256逐份核验 | 官方全文来源清单.csv；official_sources.json |','| 10题证据 | 实际接口响应、标准页、答案、引用分别评价 | 10题与改写评价.csv；http_responses.jsonl；web/ |','| 风险引文/页码存在性 | 保留原始编号，19条标题对照PDF20-23页 | 风险引文逐项核对.csv；华虹风险_PDF第*.txt/png |','| LSA改写与未校准指标 | 对照纯LSA/BM25/融合/规则补充，报告失败；不报未定义置信度 | retrieval_results.json；retrieval_summary.json |','| 全景按公司取证，召回/答案分评 | 第8、9题逐公司标准页及召回率，与回答正确性分列 | 跨公司逐家公司评价.csv |','| 第三课61-63、90-92页 | 已读指定页，增加原页阅读、覆盖缺口补查和引用白名单 | evidence_tools.py；课件要求对照.md；实际响应中的coverage/evidence_trace |','','## 更新仓库','下载并解压本修改包，将 semiconductor_qa 内的内容放在仓库根目录。不要上传 index.pkl、未压缩chunks.json、环境文件或密钥。压缩库单文件低于网页上传25MB限制。运行 python index.py 后 python app.py 即可使用随包压缩库。旧evaluation/extractive目录保留为历史测试，当前修改证据以evaluation/revision为准。','','## 自行复跑','```powershell','python -m pip install -r requirements.txt','python index.py','python -m unittest discover -s tests -v','python evaluation/evaluate_retrieval.py','python evaluation/evaluate_http.py','python app.py','```','','HTTP评价脚本只需项目依赖，不要求浏览器。浏览器测试另需playwright Chromium，可运行 python -m playwright install chromium 后把实际可执行路径传给 --browser。']
(out/'修改说明.md').write_text('\n'.join(lines))
