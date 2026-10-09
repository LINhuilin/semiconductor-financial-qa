import unittest
from decimal import Decimal
from unittest.mock import patch
from extractive import answer, financial_fact
from engine import Engine


def evidence(company='甲', unit='元', currency='人民币', current='120', previous='100',
             growth='20', old='80', source='S1', row='营业收入'):
    return {'company': company, 'year': '2025', 'page': 7, 'file': 'test.pdf',
            'kind': 'page_text', 'source': source,
            'text': f'主要会计数据\n单位：{unit} 币种：{currency}\n2025年 2024年 本期比上年增减(%) 2023年\n{row} {current} {previous} {growth} {old}\n'}


class ExtractionTests(unittest.TestCase):
    def test_future_target_is_not_report_year(self):
        result = answer('根据2025年年报，2027年营业收入是多少？', [evidence()], ['甲'])
        self.assertEqual(result['target_year'], '2027')
        self.assertEqual(result['answer_status'], 'insufficient')
        self.assertEqual(result['facts'], [])

    def test_unit_conversion_and_ranking(self):
        a = evidence('甲', unit='万元', current='12', previous='10', old='8')
        b = evidence('乙', unit='千元', current='150', previous='100', growth='50', old='80', source='S2')
        result = answer('比较甲乙2025年营业收入，统一亿元排序', [a, b], ['甲', '乙'])
        self.assertEqual(result['answer_status'], 'answered')
        self.assertEqual([Decimal(f['value_yuan']) for f in result['facts']], [Decimal(120000), Decimal(150000)])
        self.assertIn('乙 0.0015亿元 [S2] > 甲 0.0012亿元 [S1]', result['answer'])

    def test_missing_company_prevents_complete_ranking(self):
        result = answer('比较甲乙2025年营业收入并排序', [evidence()], ['甲', '乙'])
        self.assertEqual(result['answer_status'], 'partial')
        self.assertNotIn('排序：', result['answer'])
        self.assertIn('跨公司证据不完整', result['answer'])

    def test_implicit_currency_needs_same_report_note_for_ranking(self):
        a=evidence('甲');a['text']=a['text'].replace('单位：元 币种：人民币','') .replace('营业收入','营业收入（元）')
        b=evidence('乙',source='S2')
        result=answer('比较甲乙2025年营业收入', [a,b], ['甲','乙'])
        self.assertEqual(result['answer_status'],'partial')
        self.assertNotIn('排序：',result['answer'])
        note=dict(a,source='S3',page=125,text='本集团以人民币为记账本位币。')
        result=answer('比较甲乙2025年营业收入', [a,b,note], ['甲','乙'])
        self.assertEqual(result['answer_status'],'answered')
        self.assertEqual(result['facts'][0]['currency_source'],'S3')

    def test_foreign_currency_is_not_silently_converted(self):
        for currency in ('美元', '港币', '欧元'):
            with self.subTest(currency=currency):
                result = answer('甲2025年营业收入', [evidence(currency=currency)], ['甲'])
                self.assertEqual(result['answer_status'], 'insufficient')

    def test_missing_unit_is_not_guessed(self):
        h = evidence(); h['text'] = h['text'].replace('单位：元 币种：人民币\n', '')
        self.assertIsNone(financial_fact(h, 'revenue', '2025'))

    def test_wrong_percentage_column_is_rejected(self):
        result = answer('甲2025年营业收入同比多少', [evidence(growth='90')], ['甲'])
        self.assertEqual(result['answer_status'], 'insufficient')

    def test_growth_is_verified_against_previous_value(self):
        result = answer('甲2025年营业收入同比多少', [evidence()], ['甲'])
        self.assertEqual(result['facts'][0]['growth_percent'], '20')
        self.assertIn('120 ÷ 100', result['facts'][0]['growth_formula'])

    def test_zero_denominator_is_not_divided(self):
        self.assertIsNone(financial_fact(evidence(previous='0'), 'revenue', '2025', True))

    def test_conflicting_same_year_tables_are_refused(self):
        result = answer('甲2025年营业收入', [evidence(), evidence(current='150', source='S2')], ['甲'])
        self.assertEqual(result['answer_status'], 'insufficient')
        self.assertIn('冲突', result['answer'])

    def test_deducted_profit_does_not_become_attributable_profit(self):
        h = evidence(row='归属于上市公司股东的扣除非经常性损益的净利润')
        self.assertIsNone(financial_fact(h, 'profit', '2025'))

    def test_unknown_question_does_not_fabricate_answer(self):
        result = answer('甲公司的员工满意吗？', [evidence()], ['甲'])
        self.assertEqual(result['answer_status'], 'insufficient')

    def test_prose_requires_retrieved_text(self):
        h = evidence(); h['text'] = '主要产品为芯片甲、芯片乙。'
        result = answer('甲2025年的主要产品有哪些', [h], ['甲'])
        self.assertEqual(result['facts'][0]['quote'], '主要产品为芯片甲、芯片乙。')
        self.assertEqual(result['facts'][0]['source'], 'S1')

    def test_risk_does_not_list_inapplicable_categories(self):
        h = evidence(); h.update(risk_section=True, text='(一) 尚未盈利的风险\n□适用√不适用\n1、供应链风险\n')
        result = answer('甲2025年有哪些风险', [h], ['甲'])
        self.assertNotIn('尚未盈利', result['answer'])
        self.assertIn('供应链风险', result['answer'])

    def test_credentials_do_not_implicitly_enable_paid_api(self):
        engine = Engine.__new__(Engine); engine.companies = ['甲']
        with patch.dict('os.environ', {'QA_API_KEY': 'test-only', 'QA_BASE_URL': 'https://api.openai.com/v1', 'QA_MODEL': 'test-model'}), patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected network call')):
            text, generated = engine.answer('甲2025年营业收入', [evidence()])
        self.assertFalse(generated)
        self.assertIn('抽取式回答', text)


if __name__ == '__main__':
    unittest.main()
