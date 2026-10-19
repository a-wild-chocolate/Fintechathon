"""Curated official-source manifest for the first TradeX policy collection."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ROWS = [
('CN-TAX-2026', 'CN', '出口业务增值税和消费税退（免）税管理办法', 'State Taxation Administration (Shanghai official republication)', 'https://shanghai.chinatax.gov.cn/zzzb/zcwj/202602/t479288.html', 'zh', 'regulation', 'export_refund', '2026-01-30', '2026-01-01', 30),
('CN-FX-2024', 'CN', '关于进一步优化贸易外汇业务管理的通知', 'State Administration of Foreign Exchange', 'https://www.safe.gov.cn/safe/2024/0407/24204.html', 'zh', 'regulation', 'export_receipts', '2024-04-07', '2024-06-01', 30),
('CN-FX-GUIDE', 'CN', '优化贸易外汇业务管理 提升服务实体经济质效', 'State Administration of Foreign Exchange', 'https://www.safe.gov.cn/safe/2024/0407/24207.html', 'zh', 'official_explanation', 'export_receipts', '2024-04-07', None, 30),
('CN-EXPORT-CONTROL', 'CN', '中华人民共和国两用物项出口管制条例', 'Ministry of Commerce', 'https://exportcontrol.mofcom.gov.cn/article/zcfg/gnzcfg/gzjgfxwj/202410/1057.html', 'zh', 'regulation', 'export_controls', '2024-09-30', '2024-12-01', 7),
('US-IMPORT', 'US', 'Tips for New Importers and Exporters', 'US Customs and Border Protection', 'https://www.cbp.gov/trade/basic-import-export/importer-exporter-tips', 'en', 'official_guidance', 'import_procedures', None, None, 30),
('US-301', 'US', 'Section 301 Trade Remedies Frequently Asked Questions', 'US Customs and Border Protection', 'https://www.cbp.gov/trade/programs-administration/entry-summary/section-301-trade-remedies/faqs', 'en', 'official_guidance', 'trade_remedies', None, None, 1),
('US-HTS', 'US', 'Harmonized Tariff Schedule', 'US International Trade Commission', 'https://hts.usitc.gov/', 'en', 'live_lookup', 'tariff_lookup', None, None, 1),
('US-LOW-VALUE-PROPOSAL', 'US', 'Low-Value Shipments; Proposed Rule', 'US Customs and Border Protection / Government Publishing Office', 'https://www.govinfo.gov/content/pkg/FR-2026-10-08/html/2026-20650.htm', 'en', 'proposal', 'low_value_shipments', '2026-10-08', None, 7),
('EU-CUSTOMS', 'EU', 'Customs duties and procedures on imports', 'European Commission / Your Europe', 'https://europa.eu/youreurope/business/finance-and-tax/customs-and-excise-duties/customs-duties-and-procedures-imports/index_en.htm', 'en', 'official_guidance', 'import_procedures', None, None, 30),
('EU-TARIC', 'EU', 'EU Customs Tariff (TARIC)', 'European Commission / DG TAXUD', 'https://taxation-customs.ec.europa.eu/online-services/online-services-and-databases-customs/eu-customs-tariff-taric_en', 'en', 'live_lookup_guide', 'tariff_lookup', None, None, 1),
('EU-CE', 'EU', 'CE marking', 'European Commission', 'https://single-market-economy.ec.europa.eu/single-market/goods/ce-marking_en', 'en', 'official_guidance', 'product_compliance', None, None, 30),
('EU-GPSR', 'EU', 'General product safety regulation (2023)', 'EUR-Lex / Publications Office of the EU', 'https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=LEGISSUM%3A4670517', 'en', 'official_legal_summary', 'product_compliance', None, '2024-12-13', 30),
('EU-CBAM', 'EU', 'CBAM definitive regime', 'European Commission / DG TAXUD', 'https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism/cbam-definitive-regime_en', 'en', 'official_guidance', 'carbon_border', None, '2026-01-01', 7),
('UK-IMPORT', 'GB', 'Import goods into the UK: step by step', 'UK Government', 'https://www.gov.uk/import-goods-into-uk', 'en', 'official_guidance', 'import_procedures', None, None, 30),
('UK-PVA', 'GB', 'Check when you can account for import VAT on your VAT Return', 'HM Revenue & Customs', 'https://www.gov.uk/guidance/check-when-you-can-account-for-import-vat-on-your-vat-return', 'en', 'official_guidance', 'import_vat', None, None, 30),
('UK-TARIFF', 'GB', 'Trade Tariff: look up commodity codes, duty and VAT rates', 'UK Government', 'https://www.gov.uk/trade-tariff', 'en', 'live_lookup_guide', 'tariff_lookup', None, None, 1),
('SG-IMPORT', 'SG', 'Import Procedures Overview', 'Singapore Customs', 'https://www.customs.gov.sg/doing-business/import-operations/import-procedures/import-procedures-overview/', 'en', 'official_guidance', 'import_procedures', None, None, 30),
('SG-PERMIT', 'SG', 'Obtain a Customs Import Permit', 'Singapore Customs', 'https://www.customs.gov.sg/businesses/importing-goods/import-procedures/apply-customs-import-permit/', 'en', 'official_guidance', 'import_permits', None, None, 30),
('SG-RECORDS', 'SG', 'Retaining Your Trade Documents', 'Singapore Customs', 'https://www.customs.gov.sg/doing-business/import-operations/import-procedures/retaining-your-trade-documents', 'en', 'official_guidance', 'document_retention', None, None, 90),
('JP-DOCUMENTS', 'JP', '1107 Documents to be Submitted for Import Clearance', 'Japan Customs', 'https://www.customs.go.jp/english/c-answer_e/imtsukan/1107_e.htm', 'en', 'official_guidance', 'import_documents', None, None, 30),
('JP-TARIFF', 'JP', "Japan's Tariff Schedule (Statistical Code for Import)", 'Japan Customs', 'https://www.customs.go.jp/english/tariff/index.htm', 'en', 'live_lookup_guide', 'tariff_lookup', None, None, 7),
('JP-RCEP', 'JP', 'Guide to obtaining preferential tariff treatment under RCEP', 'Japan Customs', 'https://www.customs.go.jp/english/epa/rcep/rcep.html', 'en', 'official_guidance', 'preferential_origin', None, None, 30),
('AU-IMPORT', 'AU', 'Requirements to import goods', 'Australian Border Force', 'https://www.abf.gov.au/importing-exporting-and-manufacturing/importing/how-to-import/requirements', 'en', 'official_guidance', 'import_procedures', None, None, 30),
('AU-CHAFTA', 'AU', 'Guide to using ChAFTA to export or import', 'Australian Department of Foreign Affairs and Trade', 'https://www.dfat.gov.au/trade/agreements/in-force/chafta/doing-business-with-china/guide-to-using-chafta-to-export-or-import', 'en', 'official_guidance', 'preferential_origin', None, None, 30),
('VN-IMPORT', 'VN', 'Customs Procedure for Import Goods (VNACCS)', 'Vietnam Customs / Vietnam Trade Information Portal', 'https://www.vietnamtradeportal.gov.vn/index.php?id=3&r=searchProcedure/view1', 'vi', 'official_guidance', 'import_procedures', None, None, 30),
('TH-IMPORT', 'TH', 'Import procedures', 'Thai Customs / Laem Chabang Port Customs Office', 'https://lcpcb.customs.go.th/th/import-procedures', 'en-th', 'official_guidance', 'import_procedures', None, None, 30),
('RCEP-PORTAL', 'RCEP', '区域全面经济伙伴关系协定：协定正文与附件', 'Ministry of Commerce of China', 'https://fta.mofcom.gov.cn/channel/rcep.shtml', 'zh', 'official_index', 'preferential_origin', None, None, 30),
('RCEP-ORIGIN', 'RCEP', 'RCEP 第三章 原产地规则', 'Ministry of Commerce of China / RCEP treaty text', 'https://fta.mofcom.gov.cn/upload/agreementFiles/rcep/rceppdf/d3z_cn.pdf', 'zh', 'treaty', 'preferential_origin', None, None, 90),
('CN-FX-2025-QA', 'CN', '进一步便利外汇资金结算支持外贸稳定发展：政策问答', 'State Administration of Foreign Exchange', 'https://www.safe.gov.cn/safe/file/file/20251223/1d856ef316a64a3c9d13571b19f05432.pdf', 'zh', 'official_explanation', 'export_receipts', '2025-12-23', None, 30),
('CN-SZ-INSURANCE', 'CN-SZ', '2026年7—9月中小微外贸企业出口信用保险统保工作通知', 'Shenzhen Municipal Commerce Bureau', 'https://www.sz.gov.cn/cn/xxgk/zfxxgj/tzgg/content/post_12930573.html', 'zh', 'local_program_notice', 'export_credit_insurance', '2026-08-10', '2026-07-01', 30),
('CN-GZ-INSURANCE', 'CN-GZ', '组织中小微出口企业线上申领普惠出口信用保险保单的通知', 'Guangzhou Municipal Commerce Bureau', 'https://sw.gz.gov.cn/gkmlpt/content/10/10878/post_10878834.html', 'zh', 'local_program_notice', 'export_credit_insurance', None, None, 30),
('RCEP-COO', 'RCEP', 'RCEP 原产地证明最低信息要求', 'Ministry of Commerce of China / RCEP treaty text', 'https://fta.mofcom.gov.cn/upload/agreementFiles/rcep/rceppdf/d3z_fj2_cn.pdf', 'zh', 'treaty', 'origin_documents', None, None, 90),
('ICC-DAP-DDP', 'GLOBAL', 'DAP & DDP Incoterms 2020: Key differences', 'ICC Academy', 'https://academy.iccwbo.org/incoterms/article/incoterms-2020-dap-or-ddp/', 'en', 'standard_owner_explanation', 'incoterms', None, None, 90),
('EU-GPSR-FACTSHEET', 'EU', 'The new General Product Safety Regulation: Factsheet', 'European Commission / DG Justice and Consumers', 'https://commission.europa.eu/document/download/a281b150-19fd-44f9-bef8-c6018f9c4792_en?filename=new_general_product_safety_regulation_-_factsheet.pdf', 'en', 'official_explanation', 'product_compliance', '2023-07-01', '2024-12-13', 30),
]

def seed():
    records=[]
    for row in ROWS:
        keys=['source_id','jurisdiction','title','publisher','url','language','source_type','topic','published_date','effective_from','review_interval_days']
        r=dict(zip(keys,row))
        r.update(collection='tradex_public_trade', origin_scope='CN', collected_on='2026-10-18', effective_to=None,
                 legal_status='proposed_not_in_force' if r['source_type']=='proposal' else 'not_globally_adjudicated',
                 allowed_use='monitoring_only' if r['source_type']=='proposal' else 'evidence_retrieval',
                 rule_publication_status='reference_only', embedding_status='not_generated', selectors=[])
        if r['source_id']=='CN-SZ-INSURANCE':
            r.update(effective_to='2026-09-30',legal_status='coverage_period_ended',allowed_use='historical_reference')
        records.append(r)
    (ROOT/'sources.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
    print(f'Seeded {len(records)} official and standard-owner sources')

if __name__=='__main__': seed()
