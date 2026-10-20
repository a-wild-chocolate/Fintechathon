"""Shared MCP business workflows. Only explicit UI confirmation commits a forecast."""
import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, Field
from ..service import Conflict, NotFound
from ..business_records import for_model

class Workspace(BaseModel):
    version: int = Field(ge=1)
    opening: float = Field(ge=0, le=100000000)
    supplierDay: int = Field(ge=0, le=55)
    receiptDay: int = Field(ge=0, le=55)
    amountUSD: float = Field(default=12000, gt=0, le=12000)

ALLOW = {
    'coordinator': {'web_search', 'web_fetch', 'wf_status', 'kb_search', 'evidence_read'},
    'reconciliation': {'wf_status', 'kb_search', 'evidence_read', 'wf_reconcile'},
    'cash_flow': {'wf_status', 'wf_cash'},
    'decision': {'web_search', 'web_fetch', 'sandbox_python', 'wf_status', 'kb_search', 'evidence_read', 'wf_cash', 'wf_options', 'wf_draft', 'wf_financing'},
}
START = date(2026, 10, 17)

def cents(amount):
    return int((Decimal(str(amount))*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def cash(snapshot, delay=0, extension=0):
    """The current demo company's 56-day schedule, matching src/finance.js."""
    if snapshot.get('kind')=='business':
        from ..business_records import forecast
        return forecast(snapshot,delay=delay,extension=extension)
    receipt_day, supplier_day = snapshot['receiptDay']+delay, snapshot['supplierDay']+extension
    if not 0 <= receipt_day <= 55 or not 0 <= supplier_day <= 55:
        raise ValueError('Scenario dates must remain within the 56-day demo horizon.')
    net = int((Decimal(str(snapshot['amountUSD'])) / Decimal('12000') * Decimal('8000000')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    movements = snapshot.get('movements')
    scheduled = {}
    if movements:
        for movement in movements:
            due = (date.fromisoformat(movement['due_date'])-START).days
            value = movement['signed_minor']
            if movement['id'] == 'supplier': due = supplier_day
            if movement['id'] == 'receipt': due, value = receipt_day, net
            scheduled[due] = scheduled.get(due, 0) + value
    else:
        scheduled = {20: -4200000, 30: 12000000, 40: -3800000, 50: 6500000}
        scheduled[supplier_day] = scheduled.get(supplier_day, 0) - 16000000
        scheduled[receipt_day] = scheduled.get(receipt_day, 0) + net
    balance = cents(snapshot['opening']); series = []
    for day in range(56):
        balance += scheduled.get(day, 0)
        series.append({'date': str(START+timedelta(days=day)), 'balance_cny': balance/100})
    first = next((row for row in series if row['balance_cny'] < 0), None)
    return {'state_version': snapshot['version'], 'currency': 'CNY', 'opening_cny': snapshot['opening'],
            'supplier_payment_cny': 160000, 'receipt_delay_days': delay, 'supplier_extension_days': extension,
            'expected_receipt_usd': snapshot['amountUSD'], 'expected_net_cny': net/100,
            'unscheduled_usd': 12000-snapshot['amountUSD'], 'first_shortfall': first,
            'peak_shortfall_cny': max(0, -min(r['balance_cny'] for r in series)), 'daily_balances': series,
            'basis': 'Synthetic company schedule; expected USD conversion at the demo ratio 80000/12000, not bank cash.',
            'receipt_date': str(START+timedelta(days=receipt_day)), 'supplier_date': str(START+timedelta(days=supplier_day))}

class Workflows:
    def __init__(self, library, store):
        self.lib, self.store = library, store
        self.tenant = library.settings.tenant

    def execute(self, name, run_id, role, args):
        if name not in ALLOW.get(role, set()): raise ValueError('Tool is not assigned to this agent role')
        run = self.store.run(run_id, self.tenant)
        if run['request'].get('analysis_only') and name in {'wf_reconcile', 'wf_draft', 'sandbox_python'}:
            raise Conflict('Analysis-only retry cannot write financial data or create drafts.')
        if run['status'] != 'running': raise Conflict('Run is no longer active')
        if name in {'web_search', 'web_fetch', 'sandbox_python'}:
            from .extensions import Extensions
            return Extensions(self).run(name, run, args)
        request = run['request']; workspace = self.store.workspace(self.tenant)
        proposal = self.store.proposal(self.tenant, run['session_id'])
        if name == 'wf_status':
            return {'workspace': for_model(workspace), 'monetary_units':'All amounts are in major currency units (CNY yuan, USD dollars, EUR euros), never cents.', 'order_id': request.get('order_id'), 'proposal': proposal,
                    'basis': 'Saved company records and explicit planning assumptions; receipt promises are not posted cash.'}
        if name in {'kb_search', 'wf_financing'}:
            results = self.lib.search(args['query'], self.tenant, document_id=request.get('document_id'),
                                      order_id=request.get('order_id'), market=request.get('market'), limit=5)['results']
            sources = []
            for hit in results:
                sources.append({'document_id': hit['document_id'], 'version': hit['version'],
                                'locator': hit['citation']['locator'], 'source_url': hit['citation']['source_url'],
                                'original_url': hit['citation']['original_url'], 'title': hit['title'],
                                'excerpt': hit['text'], 'context': hit['context'], 'review_due': hit['review_due']})
            registered = self.store.sources(run_id, self.tenant, sources)
            keys = {(s['document_id'], s['version'], s['locator']) for s in sources}
            return {'sources': [s for s in registered if (s['document_id'], s['version'], s['locator']) in keys],
                    'purpose': 'Product-specific document readiness only; identify missing product/region/date if requirements are absent.' if name == 'wf_financing' else 'evidence'}
        if name == 'evidence_read':
            doc_id = args['document_id']
            if request.get('document_id') and doc_id != request['document_id']: raise ValueError('Outside selected document scope')
            doc = self.lib.document(doc_id, self.tenant)
            if request.get('order_id') and doc['tenant'] != 'public' and doc['metadata'].get('order_id') not in {None, '', request['order_id']}:
                raise ValueError('Document belongs to a different order')
            version = doc['current_version']
            if not version: return {'status': 'needs_information', 'reason': 'Document is still indexing'}
            sources = [{'document_id': doc_id, 'version': version, 'title': doc['title'], 'locator': p['locator'],
                        'source_url': doc['metadata'].get('source_url'), 'original_url': f'/api/documents/{doc_id}/versions/{version}/original',
                        'excerpt': p['text'], 'context': p['text'], 'review_due': None} for p in doc['content'][:8]]
            registered = self.store.sources(run_id, self.tenant, sources)
            return {'sources': [s for s in registered if s['document_id'] == doc_id and s['version'] == version],
                    'total_sections': len(doc['content']), 'sections_returned': len(sources)}
        if name == 'wf_draft':
            return self.store.artifact(self.tenant, run_id, args['kind'], args['text'])
        if not workspace: return {'status': 'needs_information', 'reason': 'Open the company dashboard to supply the demo cash schedule.'}
        if workspace.get('kind')=='business':
            from .business_workflows import execute
            return for_model(execute(self,name,self.store.run(run_id,self.tenant),args,workspace,proposal))
        if request.get('order_id') not in {None, '', 'TF-26104'}:
            return {'status': 'needs_information', 'reason': 'This order has no backend financial schedule yet. Do not reuse TF-26104 figures.'}
        if name == 'wf_reconcile':
            if request.get('order_id') != 'TF-26104': raise ValueError('Select TF-26104 to propose a receipt schedule change')
            amount = args.get('amount') if args.get('amount') is not None else args.get('amount_usd')
            receipt_date = args.get('receipt_date')
            missing = []
            if amount is None: missing.append('amount_usd')
            elif not 0 < amount <= 12000: raise ValueError('Amount must be greater than zero and at most USD 12000')
            if not receipt_date: missing.append('receipt_date')
            elif not 0 <= (date.fromisoformat(receipt_date)-START).days <= 55:
                raise ValueError('Receipt date must be inside the 56-day demo horizon')
            ids = args.get('evidence_ids', [])
            allowed = {s['id'] for s in self.store.run(run_id, self.tenant)['sources']}
            if not set(ids) <= allowed: raise ValueError('Unknown evidence reference')
            payload = {'kind': 'receipt_promise', 'order_id': 'TF-26104', 'amount_usd': amount,
                       'receipt_date': receipt_date, 'missing_fields': missing, 'evidence_ids': ids,
                       'sources': [s for s in self.store.run(run_id, self.tenant)['sources'] if s['id'] in ids],
                       'remaining_usd': 12000-amount if amount is not None else None}
            return self.store.save_proposal(run, payload, workspace['version'])
        if name in {'wf_cash', 'wf_options'}:
            scenario = dict(workspace)
            if args.get('use_proposal'):
                if not proposal or proposal['status'] != 'needs_approval': raise ValueError('A complete unconfirmed proposal is required')
                if proposal['base_version'] != workspace['version']: raise Conflict('Proposal is stale; reanalyze current state')
                scenario.update(amountUSD=proposal['amount_usd'], receiptDay=(date.fromisoformat(proposal['receipt_date'])-START).days)
            delay, extension = args.get('receipt_delay_days', 0), args.get('supplier_extension_days', 0)
            result = cash(scenario, delay, extension)
            if name == 'wf_options': return {'current': cash(workspace), 'candidate': result, 'agreement_required': True}
            return result
        raise ValueError('Unknown workflow')

    def confirm(self, proposal_id):
        with self.store.db.connect(write=True) as db:
            row = db.execute('SELECT * FROM agent_proposals WHERE id=? AND tenant=?', (proposal_id, self.tenant)).fetchone()
            if not row: raise NotFound('Proposal not found')
            if row['status'] == 'confirmed': return json.loads(row['result'])
            if row['status'] != 'needs_approval': raise Conflict('Proposal is incomplete or superseded')
            proposal = json.loads(row['payload'])
            for source in proposal['sources']:
                doc = self.lib.document(source['document_id'], self.tenant)
                if doc['current_version'] != source['version']: raise Conflict('Source changed; ask the assistant to reanalyze')
            snapshot=self.store.business.snapshot(self.tenant,db)
            if snapshot['version'] != row['base_version']: raise Conflict('Financial state changed; reanalyze before confirmation')
            if snapshot.get('kind')=='business':
                from .business_workflows import confirm
                result=confirm(self,db,proposal,snapshot)
                result['proposal_id']=proposal_id
            else:
                before=cash(snapshot)
                snapshot.update(version=snapshot['version']+1,amountUSD=proposal['amount_usd'],receiptDay=(date.fromisoformat(proposal['receipt_date'])-START).days)
                snapshot=self.store.business.write_snapshot(db,self.tenant,snapshot,'receipt_confirmation')
                result={'workspace':snapshot,'before':before,'after':cash(snapshot),'proposal_id':proposal_id,'status':'confirmed','actual_cash_changed':False}
            for source in proposal['sources']:
                db.execute('INSERT OR REPLACE INTO business_evidence VALUES(?,?,?,?,?)', (self.tenant,source['document_id'],source['version'],proposal['order_id'],'receipt_promise'))
            db.execute("UPDATE agent_proposals SET status='confirmed',result=? WHERE id=?", (json.dumps(result), proposal_id))
        return result
