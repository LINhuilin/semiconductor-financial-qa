"""Deterministic answers from retrieved evidence; no model or network calls."""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

NUMBER = re.compile(r'-?\d[\d,]*(?:\.\d+)?%?')
LABELS = ('营业收入', '归属于上市公司股', '经营活动产生的', '利润总额',
          '基本每股收益', '稀释每股收益', '资产总额', '总资产', '研发投入合计',
          '研发投入总额占营业收入比例', '研发投入资本化', '本期费用化研发投入', '本期资本化研发投入')
CURRENCY_NOTE = re.compile(r'本(?:公司|集团)(?:及境内子公司)?(?:以|采用)?\s*人民币\s*为\s*记账本位币')


def question_kind(question):
    if '风险' in question:
        return 'risk'
    if '主要产品' in question:
        return 'products'
    if '研发投入' in question:
        return 'research'
    if '净利润' in question:
        return 'profit'
    if '现金流量' in question:
        return 'cashflow'
    if '营业收入' in question or '收入' in question:
        return 'revenue'
    return 'unknown'


def requested_year(question, hits):
    years = re.findall(r'(20\d{2})\s*年', question)
    # A future target in “根据2025年报，2027年收入” must not become 2025.
    return years[-1] if years else next(iter({h['year'] for h in hits}), None)


def citation(hit):
    return f"[{hit['source']}] {hit['company']} {hit['year']}年报 PDF第{hit['page']}页（{hit['file']}）"


def decimal_string(value):
    return format(value, 'f')


def money_string(value):
    return format(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP), ',.2f')


def _row(text, prefix):
    """Keep split labels around the numeric line, stop before the next metric."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if prefix not in re.sub(r'\s+', '', line):
            continue
        collected = [line]
        for offset, following in enumerate(lines[i + 1:i + 6], i + 1):
            compact = re.sub(r'\s+', '', following)
            if any(compact.startswith(label) for label in LABELS):
                break
            collected.append(following)
            if NUMBER.search(following) and len(NUMBER.findall('\n'.join(collected))) >= 4:
                # Some PDFs append the end of the label after the numeric cells.
                if offset + 1 < len(lines) and re.match(r'^\s*(?:东)?的净利润|^\s*流量净额', lines[offset + 1]):
                    collected.append(lines[offset + 1])
                break
        raw = '\n'.join(collected).strip()
        values = NUMBER.findall(raw)
        label = re.sub(r'\s+', '', NUMBER.sub('', raw)).replace('%', '')
        if values:
            yield raw, label, values


def _unit(text, row):
    # Use the nearest preceding table unit; never use an unrelated later hint.
    pos = text.find(row)
    before = text[:pos] if pos >= 0 else ''
    units = list(re.finditer(r'单位\s*[：:]\s*(亿元|万元|千元|元)', before))
    currencies = list(re.finditer(r'币种\s*[：:]\s*([^\s；;，,]+)', before))
    currency = currencies[-1].group(1) if currencies else None
    if currency and currency != '人民币':
        return None
    if units:
        unit = units[-1].group(1)
        match = units[-1]
        end = before.find('\n', match.end())
        unit_quote = before[before.rfind('\n', 0, match.start()) + 1:end if end >= 0 else len(before)].strip()
    elif re.search(r'[（(]元[）)]', row):
        unit = '元'
        unit_quote = re.search(r'[（(]元[）)]', row).group(0)
    else:
        return None
    factor = {'元': Decimal(1), '千元': Decimal(1000),
              '万元': Decimal(10000), '亿元': Decimal(100000000)}[unit]
    return unit, factor, '人民币' if currency else '表列元口径（未单列币种）', unit_quote


def financial_fact(hit, kind, year, growth=False):
    text = hit['text']
    if '主要会计数据' not in text or hit['kind'] != 'page_text':
        return None
    prefix = {'revenue': '营业收入', 'profit': '归属于上市公司股',
              'cashflow': '经营活动产生的'}[kind]
    for raw, label, numbers in _row(text, prefix):
        if kind == 'profit' and ('净利润' not in label or '扣除' in label or '净资产' in label):
            continue
        if kind == 'cashflow' and '现金流量净额' not in label:
            continue
        if len(numbers) != 4:
            continue  # Quarterly/merged/ambiguous tables are not guessed.
        pos = text.find(raw)
        header = text[:pos].split('主要会计数据')[-1]
        years = list(dict.fromkeys(re.findall(r'(20\d{2})\s*年', header)))
        if (len(years) != 3 or year not in years or
                int(years[0]) - int(years[1]) != 1 or int(years[1]) - int(years[2]) != 1 or
                '分季度' in header):
            continue
        unit = _unit(text, raw)
        if unit is None:
            continue
        try:
            values = [Decimal(n.rstrip('%').replace(',', '')) for n in numbers]
        except InvalidOperation:
            continue
        index = {years[0]: 0, years[1]: 1, years[2]: 3}[year]
        fact = {'company': hit['company'], 'year': year, 'metric': kind,
                'value': decimal_string(values[index]), 'unit': unit[0],
                'currency': unit[2], 'unit_quote': unit[3], 'value_yuan': decimal_string(values[index] * unit[1]),
                'source': hit.get('source', ''), 'file': hit['file'], 'page': hit['page'],
                'quote': raw, 'header': header.strip()}
        if growth:
            if year != years[0] or values[1] == 0:
                continue
            computed = (values[0] / values[1] - 1) * 100
            # Check that the purported percentage column agrees with the values.
            precision = len(numbers[2].rstrip('%').split('.')[1]) if '.' in numbers[2] else 0
            tolerance = Decimal('0.5') * Decimal(10) ** -precision + Decimal('.00001')
            if abs(computed - values[2]) > tolerance:
                continue
            fact.update(growth_percent=decimal_string(values[2]),
                        previous_value=decimal_string(values[1]),
                        growth_formula=f'({values[0]} ÷ {values[1]} − 1) × 100%')
        return fact
    return None


def research_facts(hit, year):
    if hit['year'] != year or hit['kind'] != 'page_text' or '研发投入情况表' not in hit['text']:
        return None
    amounts = list(_row(hit['text'], '研发投入合计'))
    ratios = list(_row(hit['text'], '研发投入总额占营业收入比例'))
    if not amounts or not ratios:
        return None
    raw, _, values = amounts[0]
    unit = _unit(hit['text'], raw)
    if unit is None or len(values) != 1 or len(ratios[0][2]) != 1:
        return None
    return {'company': hit['company'], 'year': year, 'metric': 'research',
            'value': values[0].replace(',', ''), 'unit': unit[0],
            'currency': unit[2], 'unit_quote': unit[3], 'ratio_percent': ratios[0][2][0].rstrip('%'),
            'source': hit.get('source', ''), 'file': hit['file'], 'page': hit['page'],
            'quote': raw + '\n' + ratios[0][0]}


def prose_facts(hits, kind, year):
    facts = []
    for h in hits:
        if h['kind'] != 'page_text' or h['year'] != year:
            continue
        if kind == 'products':
            match = re.search(r'主要产品(?:为|包括|有)\s*([^。]+。)', h['text'])
            quotes = [match.group(0)] if match else []
        else:
            # Only numbered risk headings in the retrieved risk section.
            if not h.get('risk_section'):
                continue
            quotes = re.findall(r'^\s*\d+、([^\n]*风险)\s*$', h['text'], re.M)
            quotes += re.findall(r'^\s*[（(]\d+[）)]([^\n]*风险)\s*$', h['text'], re.M)
            macro = re.search(r'\(七\)\s*宏观环境风险\s*\n\s*√适用', h['text'])
            if macro:
                quotes.append(macro.group(0).strip())
        for quote in quotes:
            facts.append({'company': h['company'], 'year': year, 'metric': kind,
                          'source': h['source'], 'file': h['file'], 'page': h['page'],
                          'quote': quote.strip()})
    return facts


def answer(question, hits, companies):
    kind = question_kind(question)
    year = requested_year(question, hits)
    growth = '同比' in question or '增速' in question
    facts, warnings, lines = [], [], []
    hit_by_source = {h['source']: h for h in hits}
    if not year or kind == 'unknown':
        warnings.append('当前规则不能可靠抽取此类问题，请核对下方候选原文。')
    else:
        for company in companies:
            candidates = [h for h in hits if h['company'] == company]
            if kind in ('revenue', 'profit', 'cashflow'):
                alternatives = [f for h in candidates if (f := financial_fact(h, kind, year, growth))]
                identities = {(f['value_yuan'], f.get('growth_percent')) for f in alternatives}
                if len(identities) > 1:
                    warnings.append(f'{company}：召回表格的同年指标有冲突，未选择或排序。')
                    continue
                found = alternatives[:1]
                for fact in found:
                    if fact['currency'].startswith('表列元'):
                        notes = [(h, CURRENCY_NOTE.search(h['text'])) for h in candidates
                                 if h['year'] == year and h['kind'] == 'page_text']
                        notes = [(h, m) for h, m in notes if m]
                        if notes:
                            h, match = notes[0]
                            fact.update(currency='人民币（同报告本位币说明核对）',
                                        currency_source=h['source'], currency_quote=match.group(0),
                                        currency_page=h['page'])
                        elif len(companies) > 1:
                            warnings.append(f'{company}：金额表未单列币种，未找到人民币本位币补充证据，不作跨币种排名。')
            elif kind == 'research':
                found = [f for h in candidates if (f := research_facts(h, year))][:1]
            else:
                found = prose_facts(candidates, kind, year)
            if not found:
                warnings.append(f'{company}：当前召回证据不足，未能可靠提取{year}年所问指标/内容；不据此推断公司未披露。')
            facts.extend(found)
    for f in facts:
        cite = citation(hit_by_source[f['source']])
        if f['metric'] in ('products', 'risk'):
            lines.append(f"{f['company']} {year}年原文摘录：{f['quote']}\n来源：{cite}")
        elif f['metric'] == 'research':
            lines.append(f"{f['company']} {year}年研发投入合计：{money_string(Decimal(f['value']))}{f['unit']}；占营业收入{f['ratio_percent']}%。\n来源：{cite}\n原文：{f['quote']}")
        else:
            name = {'revenue': '营业收入', 'profit': '归属于上市公司股东的净利润',
                    'cashflow': '经营活动产生的现金流量净额'}[f['metric']]
            value = money_string(Decimal(f['value'])) if f['unit'] == '元' else f['value']
            sentence = f"{f['company']} {year}年{name}：{value}{f['unit']}（{f['currency']}）"
            if 'growth_percent' in f:
                sentence += f"；同比{f['growth_percent']}%（公式：{f['growth_formula']}，与表列增速核对）"
            lines.append(sentence + f"。\n来源：{cite}\n单位原文：{f['unit_quote']}\n指标原文：{f['quote']}")
            if 'currency_source' in f:
                lines.append(f"{f['company']}币种依据：{f['currency_quote']}。\n来源：{citation(hit_by_source[f['currency_source']])}")
    if len(companies) > 1 and kind == 'revenue':
        if len(facts) == len(companies) and not warnings:
            key = 'growth_percent' if growth else 'value_yuan'
            ordered = sorted(facts, key=lambda f: Decimal(f[key]), reverse=True)
            if growth:
                lines.append('同比增速排序：' + ' > '.join(f"{f['company']} {f['growth_percent']}% [{f['source']}]" for f in ordered))
                lines.append('最高：' + ordered[0]['company'] + '（只比较所选公司、同年度和同一营业收入口径）。')
            else:
                lines.append('统一人民币亿元：各表列数值 × 单位换算系数 ÷ 100,000,000；不进行外币换算。')
                lines.append('排序：' + ' > '.join(f"{f['company']} {decimal_string(Decimal(f['value_yuan']) / Decimal(100000000))}亿元 [{f['source']}]" for f in ordered))
        else:
            warnings.append('跨公司证据不完整或存在冲突，不给出完整排名或“最高”结论。')
    if kind == 'risk' and facts:
        lines.append('以上为召回风险章节的标题摘录；不适用的风险项不计入，不能保证覆盖报告中每一处风险披露。')
    if not facts:
        lines.append('证据不足：无法从当前召回原文可靠回答。历史年报数值不能充当未来年份的确定收入。' if kind == 'revenue' else '证据不足：无法从当前召回原文可靠回答。')
    lines.extend(warnings)
    return {'answer': '抽取式回答（规则抽取 / Python计算，非大模型生成）\n\n' + '\n\n'.join(lines),
            'generated': False, 'answer_mode': 'extractive',
            'answer_status': 'partial' if facts and warnings else 'answered' if facts else 'insufficient',
            'facts': facts, 'warnings': warnings, 'target_year': year}
