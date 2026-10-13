import re
from decimal import Decimal

def compact(text):
    return re.sub(r'\s+', '', text)


def check_response(row, result, references, chunks, pdfs):
    errors = []
    reference = references[row['题号']]
    facts = result.get('facts', [])
    hits = {h['source']: h for h in result.get('hits', [])}
    citations = []
    for fact in facts:
        h = hits.get(fact['source'])
        if not h or any(fact[k] != h[k] for k in ('company', 'file', 'page')):
            errors.append('事实来源元数据与召回不一致'); continue
        if h['year'] != '2025' or fact['year'] != '2025':
            errors.append('年份错误')
        if compact(fact['quote']) not in compact(h['text']):
            errors.append('抽取引文不在召回文本中')
        original = pdfs[h['file']][h['page'] - 1].get_text(sort=True)
        if compact(fact['quote']) not in compact(original):
            errors.append('引用原文不在对应PDF页')
        if fact.get('unit_quote') and compact(fact['unit_quote']) not in compact(original):
            errors.append('单位引文不在对应PDF页')
        if fact.get('currency_source'):
            note=hits.get(fact['currency_source'])
            if not note or note['company']!=fact['company'] or note['year']!='2025':
                errors.append('本位币引用公司/报告年度错误')
            else:
                note_text=pdfs[note['file']][note['page']-1].get_text(sort=True)
                if compact(fact['currency_quote']) not in compact(note_text): errors.append('本位币引文不在对应PDF页')
        if h.get('chunk_ids'):
            merged = '\n'.join(chunks[c]['text'] for c in h['chunk_ids'])
            if merged != h['text']:
                errors.append('同页上下文不等于记录分块合并')
        if f"[{fact['source']}]" not in result['answer'] or f"PDF第{h['page']}页" not in result['answer']:
            errors.append('回答未列明引用或PDF页码')
        citations.append({'source':fact['source'],'company':fact['company'],'pdf_page':fact['page'],
                          'quote_in_actual_pdf':compact(fact['quote']) in compact(original)})
    if result.get('generated') is not False or result.get('answer_mode') != 'extractive':
        errors.append('回答类型标记错误')
    if row['题号'] == '10':
        if result.get('answer_status') != 'insufficient' or facts or result.get('target_year') != '2027':
            errors.append('未来确定收入未正确拒答')
        if '证据不足' not in result['answer']:
            errors.append('缺少明确的证据不足提示')
    else:
        if result.get('answer_status') != 'answered': errors.append('所需答案未完整抽取')
        for company, expected in reference['expected_facts'].items():
            found = [f for f in facts if f['company'] == company]
            if len(found) != 1:
                errors.append(company+'指标缺失或重复'); continue
            fact = found[0]
            for key, value in expected.items():
                if key == 'page':
                    correct = fact.get(key) == value
                elif key == 'unit':
                    correct = fact.get(key) == value
                else:
                    try: correct = Decimal(fact.get(key, 'NaN')) == Decimal(value)
                    except Exception: correct = False
                if not correct: errors.append(company+' '+key+' 与PDF参考值不符')
            pdftext = compact(pdfs[fact['file']][fact['page'] - 1].get_text(sort=True)).replace(',', '')
            for key in ('value', 'growth_percent', 'ratio_percent'):
                if key in expected and expected[key] not in pdftext:
                    errors.append(company+' 参考'+key+'未在PDF找到')
        for phrase in reference.get('required_quotes', []):
            if phrase not in compact(result['answer']): errors.append('遗漏内容：'+phrase)
        if row['题号'] == '7' and '尚未盈利的风险' in result['answer']:
            errors.append('把不适用风险列入答案')
        if 'expected_order' in reference:
            field = 'value_yuan' if row['题号'] == '8' else 'growth_percent'
            try:
                ordered = sorted(facts,key=lambda f:Decimal(f[field]),reverse=True)
                if [f['company'] for f in ordered] != reference['expected_order']: errors.append('排名错误')
                ranking = result['answer'].split('排序：')[-1]
                positions = [ranking.find(c) for c in reference['expected_order']]
                if -1 in positions or positions != sorted(positions): errors.append('网页回答排序不符')
                if row['题号'] == '8':
                    for f in facts:
                        converted = format(Decimal(f['value_yuan'])/Decimal(100000000), 'f')
                        if converted+'亿元' not in result['answer']: errors.append('亿元换算错误')
                elif '最高：澜起科技' not in result['answer']: errors.append('最高增速结论错误')
            except Exception: errors.append('排名所需数字缺失')
    return errors, citations


