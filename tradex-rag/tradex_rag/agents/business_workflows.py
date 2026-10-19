"""Financial tools for arbitrary saved company orders."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from ..business_records import forecast, minor
from ..service import Conflict, NotFound

def execute(workflows, name, run, args, snapshot, proposal):
    order_id=run['request'].get('order_id')
    order=next((o for o in snapshot['orders'] if o['id']==order_id),None)
    if order_id and not order: raise NotFound('Selected order does not exist in this company.')
    if name=='wf_reconcile':
        if not order: raise ValueError('Select an order before proposing a receipt.')
        if order['status'] in ('completed','cancelled'): raise Conflict('This order has no active receipt plan.')
        amount=args.get('amount') if args.get('amount') is not None else args.get('amount_usd')
        currency=args.get('currency') or order['currency']
        if currency!=order['currency']: raise ValueError('Receipt currency must match the order.')
        outstanding=order['total']-order['received']-order['adjustment']
        missing=[]
        if amount is None: missing.append('amount_usd' if currency=='USD' else 'amount')
        elif not 0<amount<=outstanding: raise ValueError('Receipt must be positive and no greater than the outstanding balance.')
        receipt_date=args.get('receipt_date')
        if not receipt_date: missing.append('receipt_date')
        elif date.fromisoformat(receipt_date)<date.fromisoformat(snapshot['planning_start']): raise ValueError('Receipt precedes the opening balance date.')
        ids=args.get('evidence_ids',[])
        if not set(ids)<={s['id'] for s in run['sources']}: raise ValueError('Unknown evidence reference.')
        payload={'kind':'receipt_promise','order_id':order_id,'amount':amount,'currency':currency,
                 'amount_usd':amount if currency=='USD' else None,'receipt_date':receipt_date,'missing_fields':missing,
                 'evidence_ids':ids,'sources':[s for s in run['sources'] if s['id'] in ids],
                 'remaining':outstanding-amount if amount is not None else None,'fx_rate':order['fx_rate']}
        return workflows.store.save_proposal(run,payload,snapshot['version'])
    scenario=deepcopy(snapshot)
    if args.get('use_proposal'):
        if not proposal or proposal['status']!='needs_approval' or proposal['base_version']!=snapshot['version']:
            raise Conflict('use_proposal requires an unconfirmed complete proposal. Confirmed payments are already in saved state; use use_proposal=false to compare their timing.')
        if proposal['order_id']!=order_id: raise Conflict('Proposal belongs to a different order.')
        apply_receipt(scenario,proposal)
    delay=args.get('receipt_delay_days',0);extension=args.get('supplier_extension_days',0)
    if (delay or extension) and not order: raise ValueError('Select the order whose payment timing should change.')
    result=forecast(scenario,order_id,delay,extension)
    if name=='wf_options': return {'current':forecast(snapshot,order_id),'candidate':result,'agreement_required':True}
    if name=='wf_cash': return result
    raise ValueError('Unknown financial workflow.')

def apply_receipt(snapshot, proposal):
    order=next(o for o in snapshot['orders'] if o['id']==proposal['order_id'])
    amount=proposal['amount'];order.update(expected=amount,receipt_date=proposal['receipt_date'])
    snapshot['movements']=[m for m in snapshot['movements'] if not (m['order_id']==order['id'] and m['status']=='expected')]
    snapshot['movements'].append({'id':order['id']+':receipt','order_id':order['id'],'counterparty_id':'customer:'+order['id'],
        'label':'Expected receipt · '+order['id'],'due_date':proposal['receipt_date'],'currency':'CNY',
        'signed_minor':minor(Decimal(str(amount))*Decimal(str(order['fx_rate']))),'status':'expected',
        'original_currency':order['currency'],'original_minor':minor(amount),'conversion_basis':str(order['fx_rate'])})

def confirm(workflows, db, proposal, snapshot):
    before=forecast(snapshot,proposal['order_id']);apply_receipt(snapshot,proposal)
    movement=snapshot['movements'][-1];tenant=workflows.tenant
    saved_order=db.execute('SELECT customer_id FROM trade_orders WHERE company_id=? AND id=?',(tenant,proposal['order_id'])).fetchone()
    movement['counterparty_id']=saved_order['customer_id']
    order=next(o for o in snapshot['orders'] if o['id']==proposal['order_id'])
    supplier=db.execute("SELECT counterparty_id FROM cash_movements WHERE company_id=? AND order_id=? AND status='obligation' LIMIT 1",(tenant,order['id'])).fetchone()
    db.execute('INSERT OR IGNORE INTO order_terms VALUES(?,?,?,?,?,?,?,?)',(tenant,order['id'],minor(order['expected']),order['receipt_date'],str(order['fx_rate']),supplier[0] if supplier else None,minor(order['supplier_amount']),order['supplier_date']))
    db.execute('UPDATE order_terms SET expected_minor=?,receipt_date=? WHERE company_id=? AND order_id=?',
               (minor(proposal['amount']),proposal['receipt_date'],tenant,proposal['order_id']))
    db.execute("DELETE FROM cash_movements WHERE company_id=? AND order_id=? AND status='expected'",(tenant,proposal['order_id']))
    db.execute('INSERT INTO cash_movements VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(tenant,*[movement[k] for k in ('id','order_id','counterparty_id','label','due_date','currency','signed_minor','status','original_currency','original_minor','conversion_basis')]))
    updated=workflows.store.business.record_revision(db,tenant,'receipt_confirmed:'+proposal['order_id'])
    return {'workspace':updated,'before':before,'after':forecast(updated,proposal['order_id']),'status':'confirmed','actual_cash_changed':False}
