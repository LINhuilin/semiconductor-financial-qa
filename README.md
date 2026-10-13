# 半导体上市公司2025年报问答

包含10份2025年报，已逐份下载巨潮官方全文并验证SHA256与提交文件完全一致。完整URL、版本及核验记录见 evaluation/revision/官方全文来源清单.csv。华虹使用2026-05-15修订版。

## 2026-10-13批改修改版
当前证据请以 evaluation/revision 为准；evaluation/extractive 是修改前历史记录。提供 data/chunks.json.gz 和 data/knowledge_base.sqlite.gz 两份压缩建库产物。index.py和engine.py可直接读取压缩JSON；SQLite解压后可用SQLite工具查表。默认无需API。10原题+10受控改写、按公司召回评价、LSA消融、风险原页核验及新网页截图均已补充。测试局限见一页结论。

## Windows运行（建议Python 3.11或3.12）
解压到一个固定文件夹，在该文件夹地址栏输入 powershell 回车。以下命令逐行运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe build.py
.\.venv\Scripts\python.exe index.py
.\.venv\Scripts\python.exe app.py
```
程序绑定本机127.0.0.1，浏览器打开 http://127.0.0.1:8501 。不需要管理员权限。关闭用Ctrl+C。
原仓库没有分块；本修改版附压缩分块库，可安装依赖后直接运行index.py。需要从PDF重建时先运行 `.\.venv\Scripts\python.exe build.py`，再运行 index.py 和 app.py。build.py会重建data中的清单和提取错误记录，更换数据前请保留自己的修改。index.py在本机建立LSA索引，避免不同软件版本的索引兼容问题。日后索引加载失败时也可执行：

```powershell
.\.venv\Scripts\python.exe index.py
.\.venv\Scripts\python.exe app.py
```

## 明确区分三种能力
1. 原文检索：展示候选证据和页码，本身不等于回答。
2. **当前网页默认运行抽取式问答**：无需API，从召回的原文页提取已支持的财务指标、产品句子和风险标题，使用Python Decimal核对同比、换算元/千元/万元/亿元并排序。回答与JSON标记answer_mode=extractive、generated=false；有年度、单位、指标冲突或公司证据缺失时说明证据不足，不给完整排名。未单列币种的“（元）”表会补充召回同报告本位币说明并列明出处，跨公司缺少币种依据时不给出完整排名；遇到显式外币不自动换算人民币。这是规则抽取和计算，不能冒充大模型生成，也不是任意自然语言问题都能回答。
3. 大模型生成：未在当前网页启用、未测试。保留的Engine.generate方法仅供后续显式集成；需要QA_ENABLE_LLM=1以及以下三个变量，网页/ask不会因变量已设置而自动调用API。不得将抽取式回答评价记为大模型生成评价。

```powershell
$env:QA_BASE_URL="服务商提供的API基础地址（通常以/v1结尾）"
$env:QA_MODEL="你开通的模型名称"
$env:QA_API_KEY="你的密钥"
.\.venv\Scripts\python.exe app.py
```
以上变量只供可选生成接口集成，设置它们后当前网页查询仍为抽取式模式，不发送API请求。后续若显式启用并调用生成接口，问题和证据会发送至所配置服务，远程API可能计费；失败不能伪造模型回答。

## 向量索引
默认是TF-IDF经TruncatedSVD降维的128维LSA向量，余弦相似度与BM25通过RRF融合。它属于向量检索基线，不是预训练神经语义嵌入；同义改写能力有限。若课堂要求预训练嵌入，使用下列命令升级；首次需下载模型，可能受到网络限制，也可以使用已下载模型的本地路径：

```powershell
.\.venv\Scripts\python.exe -m pip install sentence-transformers
.\.venv\Scripts\python.exe index.py --model "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
.\.venv\Scripts\python.exe app.py
```
神经索引构建和API生成在交付环境中未验证，需在本机运行后记录真实结果。不要把默认LSA描述成神经嵌入。

## 数据处理
build.py提取每页文字和可识别表格。正文切成约650字符的块；表格按行保留表头。块含公司、年度、检测到的章节及PDF页序。跨页表格不会自动完美恢复，表头识别错误、复杂合并单元格、单位遗漏须人工回查PDF。data/extraction_errors.json记录异常，inventory记录页数、表数和哈希。
更换材料时：先运行python build.py，再运行python index.py。索引与分块必须同步重建。章节按节标题识别，遇到异常以原PDF为准。

多公司题应在页面选择所有相关公司。检索分别为各公司召回并轮询合并，减少全局top-k遗漏公司；跨公司题仍需核对是否有全部公司的有效依据。来源为PDF第几页，不强行等同印刷页码。RRF参数60，每路每公司召回200条，再限制每页最多2条以减少重复表格行挤占召回；财务指标问题使用规则查询扩展。

## 测试与提交
方案A实测材料位于evaluation/extractive/：10题实际网页响应、评价表、截图及一页结论。参考答案从上传PDF核对整理，官方全文已核验，历史记录中的“待核验”是当时状态；测试通过仅针对本次固定题集的抽取式任务。运行规则边界测试：`python -m unittest discover -s tests -v`。网页端到端评价脚本为evaluation/test_extractive_web.py，需另外安装playwright和可用Chromium；它在独立进程测试，可通过命令行指定运行副本、浏览器路径与输出目录，不访问付费API。
按evaluation/questions.csv逐题运行。测试表中的标准答案、标准页码先人工从原PDF核验。填写召回内容、答案、正确性、引用正确性和失败原因；不可仅据模型输出评判模型。
页面可下载每次问答JSON；evaluation/runs.jsonl会自动记录查询。保留至少2道跨公司全景题。
截图建议：页面总览、单公司带引用答案、全景答案及多家公司依据、失败案例。evaluation/结论模板.md目前是待填模板，不含虚构准确率。
提交代码仓库、截图、10题记录和一页结论。仓库链接需自行在GitHub等平台创建，压缩包本身不是线上仓库。
补充财报官方URL；不要提交API密钥。仅加载自己生成的pickle索引，不要加载不可信来源的pickle。

## 参考文档
- https://pymupdf.readthedocs.io/en/latest/page.html
- https://www.sbert.net/docs/package_reference/sentence_transformer/model.html
- https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.TruncatedSVD.html

## 课件对照补改
已对照第三课第61-63、90-92和163页。Engine.respond会回读所引用的原PDF页，记录evidence_trace和引用白名单；coverage按公司显示已覆盖、部分或缺据。风险章节缺页时逐页补查，最多40次read调用，预算不足保留缺口并返回部分回答。规则抽取不是LLM Agent；GraphRAG和生成模型为课件示例，本项目没有宣称实现。第163页A作业明确要求向量+BM25与带出处页面，并未明确规定必须付费API。
