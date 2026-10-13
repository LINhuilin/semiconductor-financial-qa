"""Run real browser tasks; grade only after each response against PDF-backed references.

Requires playwright + Chromium in the test environment (not app dependencies).
Example: python evaluation/test_extractive_web.py --runtime /path/to/runtime \
  --browser /usr/bin/chromium --output evaluation/extractive
"""
import argparse
import csv
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
import fitz
from playwright.sync_api import sync_playwright


from evaluation_checks import check_response

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--runtime',type=pathlib.Path,required=True)
    ap.add_argument('--output',type=pathlib.Path,required=True)
    ap.add_argument('--browser',default='/usr/bin/chromium')
    args=ap.parse_args(); root=args.runtime.resolve(); out=args.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    started_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    refs=json.loads(pathlib.Path(__file__).with_name('reference_answers.json').read_text(encoding='utf-8'))
    rows=list(csv.DictReader((root/'evaluation/questions.csv').open(encoding='utf-8-sig',newline='')))
    chunks={h['id']:h for h in json.loads((root/'data/chunks.json').read_text(encoding='utf-8'))}
    pdfs={p.name:fitz.open(p) for p in (root/'reports').glob('*.pdf')}
    log=(out/'server.log').open('w',encoding='utf-8')
    # Any outbound urllib API attempt fails this test, even if QA secrets are injected.
    code="import app,urllib.request; exec('def forbid(*args,**kwargs):\\n raise RuntimeError(\"API request forbidden in extractive evaluation\")'); urllib.request.urlopen=forbid; server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler); print(server.server_address[1],flush=True); server.serve_forever()"
    proc=subprocess.Popen([sys.executable,'-u','-c',code],cwd=root,stdout=subprocess.PIPE,stderr=log,text=True)
    results=[];responses=[];graded=[]
    try:
        portline=proc.stdout.readline().strip()
        if not portline.isdigit():raise RuntimeError('Server failed; inspect server.log')
        url='http://127.0.0.1:'+portline
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=args.browser,headless=True)
            page=browser.new_page(viewport={'width':1280,'height':1000},device_scale_factor=1)
            page.goto(url);page.locator('#companies input').nth(9).wait_for()
            page.screenshot(path=str(out/'01-overview.png'),full_page=True)
            for row in rows:
                names=row['选择公司'].split('、')
                for checkbox in page.locator('#companies input').all():checkbox.set_checked(checkbox.input_value() in names)
                page.locator('#q').fill(row['问题'])
                start=time.monotonic()
                with page.expect_response(lambda r:r.url==url+'/ask' and r.request.method=='POST') as event:page.locator('#ask').click()
                response=event.value;result=response.json();elapsed=time.monotonic()-start
                if response.status==200:
                    page.wait_for_function("!document.querySelector('#ask').disabled")
                    errors,citations=check_response(row,result,refs,chunks,pdfs)
                else:errors=['HTTP '+str(response.status)+': '+str(result.get('error'))];citations=[]
                passed=not errors
                results.append({'question':row['题号'],'type':row['题型'],'http_status':response.status,
                                'answer_correct':passed,'citation_correct':bool(citations) and all(c['quote_in_actual_pdf'] for c in citations) if row['题号']!='10' else None,
                                'errors':errors,'citations':citations,'elapsed_seconds':round(elapsed,3),
                                'answer_mode':result.get('answer_mode'),'generated':result.get('generated'),
                                'reference_status':refs[row['题号']]['reference_status']})
                responses.append(result)
                evaluated=dict(row)
                evaluated.update({'人工标准答案':refs[row['题号']]['reference_answer']+'【PDF核对参考，待人工复核】',
                                  '标准PDF页码':json.dumps(refs[row['题号']]['reference_pages'],ensure_ascii=False),
                                  '召回片段ID':'、'.join(h['id'] for h in result.get('hits',[])),
                                  '系统回答':result.get('answer',result.get('error','')),
                                  '回答是否正确':'正确（抽取式题集检查）' if passed else '错误/不完整',
                                  '出处是否正确':'不适用：证据不足拒答无数值引用' if row['题号']=='10' else '正确（与实际PDF页原文一致）' if all(c['quote_in_actual_pdf'] for c in citations) and citations else '不完整/错误',
                                  '错误原因':'无本次规则检查发现的错误；仍待人工复核' if passed else '；'.join(errors)})
                graded.append(evaluated)
                if row['题号'] in ('1','7','8','9','10'):
                    filename={'1':'02-single-answer','7':'03-risk-answer','8':'04-cross-revenue','9':'05-cross-growth','10':'06-insufficient-evidence'}[row['题号']]
                    page.screenshot(path=str(out/(filename+'.png')),full_page=True)
                print(row['题号'],'PASS' if passed else 'FAIL',errors,flush=True)
            # Exercise download through the real page and compare its payload.
            with page.expect_download() as download:page.locator('#download').click()
            path=out/'downloaded-question-10.json';download.value.save_as(path)
            assert json.loads(path.read_text(encoding='utf-8'))==responses[-1]
            first=responses[0]['facts'][0]
            target=next(h['pdf_url'] for h in responses[0]['hits'] if h['source']==first['source'])
            pdfresponse=page.request.get(url+target.split('#')[0]);assert pdfresponse.status==200 and pdfresponse.body().startswith(b'%PDF')
            assert page.request.get(url+'/reports/%2e%2e%2fREADME.md').status==404
            bad=page.request.post(url+'/ask',data={'question':'','companies':[]});assert bad.status==400
            bad=page.request.post(url+'/ask',data={'question':'收入','companies':['未在清单的公司']});assert bad.status==400
            # A visible, genuine evidence-insufficient case for unsupported indicators.
            page.locator('#q').fill('兆易创新2025年员工满意度是多少？')
            with page.expect_response(lambda r:r.url==url+'/ask') as event:page.locator('#ask').click()
            assert event.value.json()['answer_status']=='insufficient'
            page.wait_for_function("!document.querySelector('#ask').disabled")
            page.screenshot(path=str(out/'07-unsupported-question.png'),full_page=True)
            browser.close()
        (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        (out/'web-responses.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in responses)+'\n',encoding='utf-8')
        with (out/'questions.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(graded)
        summary={'executed':len(results),'correct':sum(r['answer_correct'] for r in results),
                 'failed':sum(not r['answer_correct'] for r in results),'cross_company_executed':sum(r['type']=='跨公司全景' for r in results),
                 'model_generation_tests':0,'mode':'extractive','reference_status':'上传PDF核对的有限题集；非独立教师评分',
                 'started_at':started_at,'completed_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                 'application_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('app.py','engine.py','extractive.py','page.html')},
                 'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'reports').glob('*.pdf')},
                 'extra_checks':['JSON下载与实际响应一致','原PDF端点','路径穿越拒绝','空问题400','未知公司400','未知指标证据不足']}
        (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in summary.items() if k!='source_sha256'},ensure_ascii=False))
        return 0 if len(results)==10 and all(r['answer_correct'] for r in results) else 1
    finally:
        proc.terminate()
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
        log.close()
        for doc in pdfs.values():doc.close()


if __name__=='__main__':sys.exit(main())
