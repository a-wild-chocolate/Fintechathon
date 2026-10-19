"""Company and order commands shared by the UI and financial tools."""
import json
import time
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from .service import Conflict, NotFound

Money = Decimal

def minor(value):
    return int((Decimal(str(value))*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

class CompanyInput(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    country: str = Field(default='CN',min_length=2,max_length=2)
    planning_start: date
    opening_cny: Money = Field(ge=0,max_digits=16,decimal_places=2)
    opening_usd: Money = Field(default=0,ge=0,max_digits=16,decimal_places=2)

class OrderInput(BaseModel):
    id: str = Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
    version: int = Field(ge=1)
    customer: str = Field(min_length=1,max_length=160)
    country: str = Field(default='',max_length=80)
    goods: str = Field(min_length=1,max_length=300)
    currency: Literal['USD','CNY','EUR','GBP'] = 'USD'
    total: Money = Field(gt=0,max_digits=16,decimal_places=2)
    received: Money = Field(default=0,ge=0,max_digits=16,decimal_places=2)
    expected: Money = Field(default=0,ge=0,max_digits=16,decimal_places=2)
    receipt_date: date | None = None
    fx_rate: Decimal = Field(default=1,gt=0,le=1000,max_digits=12,decimal_places=6)
    supplier: str = Field(default='',max_length=160)
    supplier_amount: Money = Field(default=0,ge=0,max_digits=16,decimal_places=2)
    supplier_date: date | None = None
    status: Literal['preparing','shipped','completed','cancelled'] = 'preparing'

    @model_validator(mode='after')
    def consistent(self):
        if self.received > self.total: raise ValueError('Received amount exceeds the order value.')
        if self.expected > self.total-self.received: raise ValueError('Expected receipt exceeds the outstanding balance.')
        if self.expected and not self.receipt_date: raise ValueError('Enter the expected receipt date.')
        if self.supplier_amount and (not self.supplier.strip() or not self.supplier_date):
            raise ValueError('Enter the supplier and payment date.')
        if self.currency == 'CNY': self.fx_rate=Decimal(1)
        if self.status == 'completed' and self.received != self.total:
            raise ValueError('A completed order must be fully settled.')
        self.customer=self.customer.strip();self.goods=self.goods.strip()
        if not self.customer or not self.goods: raise ValueError('Customer and goods cannot be blank.')
        return self

def forecast(snapshot, order_id=None, delay=0, extension=0):
    start=date.fromisoformat(snapshot['planning_start'])
    events=[]
    for row in snapshot['movements']:
        movement=dict(row)
        if row['status']=='posted': continue  # Opening balances already include posted history.
        if order_id and row['order_id']==order_id:
            shift=delay if row['signed_minor']>0 else extension
            movement['due_date']=str(date.fromisoformat(row['due_date'])+timedelta(days=shift))
        events.append(movement)
    scheduled={}
    for row in events:
        if row['currency']=='CNY': scheduled[row['due_date']]=scheduled.get(row['due_date'],0)+row['signed_minor']
    balance=minor(snapshot['opening']); series=[]
    for offset in range(56):
        day=str(start+timedelta(days=offset));balance+=scheduled.get(day,0)
        series.append({'date':day,'balance_cny':balance/100})
    first=next((r for r in series if r['balance_cny']<0),None)
    end=series[-1]['date']
    outstanding=[{'order_id':o['id'],'currency':o['currency'],
                  'amount':max(0,o['total']-o['received']-o['adjustment']-o['expected'])}
                 for o in snapshot['orders'] if o['status'] not in ('completed','cancelled')]
    return {'state_version':snapshot['version'],'currency':'CNY','opening_cny':snapshot['opening'],
            'first_shortfall':first,'peak_shortfall_cny':max(0,-min(r['balance_cny'] for r in series)),
            'daily_balances':series,'movements':events,'unscheduled_balances':outstanding,
            'outside_horizon':[r for r in events if not str(start)<=r['due_date']<=end],
            'receipt_delay_days':delay,'supplier_extension_days':extension,'selected_order':order_id,
            'basis':'Company-wide CNY availability, using saved order conversion assumptions; expected receipts are not bank cash.'}

def for_model(value):
    """Tools expose major currency units; SQLite retains integer minor units."""
    if isinstance(value,list): return [for_model(item) for item in value]
    if not isinstance(value,dict): return value
    names={'opening_minor':'opening_balance','signed_minor':'amount','original_minor':'original_amount',
           'expected_minor':'expected_amount','supplier_minor':'supplier_amount','total_minor':'total',
           'received_minor':'received','adjustment_minor':'adjustment'}
    return {names.get(key,key):(item/100 if item is not None else None) if key in names else for_model(item)
            for key,item in value.items()}


class BusinessRecords:
    def is_managed(self, tenant, db):
        return bool(db.execute('SELECT 1 FROM company_access WHERE company_id=?',(tenant,)).fetchone())

    def list_companies(self, owner):
        with self.db.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM companies WHERE id=? OR id IN (SELECT company_id FROM company_access WHERE owner=?) ORDER BY created_at',(owner,owner))]

    def check_company(self, owner, company):
        if company not in {r['id'] for r in self.list_companies(owner)}: raise NotFound('Company not found.')

    def create_company(self, owner, body):
        ident=str(uuid4());name=body.name.strip()
        if not name: raise ValueError('Enter a company name.')
        with self.db.connect(write=True) as db:
            db.execute('INSERT INTO companies VALUES(?,?,?,?,?,?,?)',(ident,name,body.country.upper(),'CNY',str(body.planning_start),1,time.time()))
            db.execute('INSERT INTO company_access VALUES(?,?)',(owner,ident))
            db.executemany('INSERT INTO bank_accounts VALUES(?,?,?,?,?,?,?)',[
                (ident,'cny-operating','CNY operating account','CNY',minor(body.opening_cny),str(body.planning_start),0),
                (ident,'usd-account','USD account','USD',minor(body.opening_usd),str(body.planning_start),0)])
            self.record_revision(db,ident,'company_created',increment=False)
        return self.overview(ident)

    def order_records(self, tenant, db):
        rows=db.execute('SELECT o.*,p.name customer,p.country FROM trade_orders o JOIN counterparties p ON p.company_id=o.company_id AND p.id=o.customer_id WHERE o.company_id=? ORDER BY o.id',(tenant,)).fetchall()
        result=[]
        for row in rows:
            o=dict(row); term=db.execute('SELECT * FROM order_terms WHERE company_id=? AND order_id=?',(tenant,o['id'])).fetchone()
            moves=[dict(r) for r in db.execute('SELECT * FROM cash_movements WHERE company_id=? AND order_id=?',(tenant,o['id']))]
            incoming=next((r for r in moves if r['signed_minor']>0),None);outgoing=next((r for r in moves if r['signed_minor']<0),None)
            supplier=db.execute('SELECT name FROM counterparties WHERE company_id=? AND id=?',(tenant,term['supplier_id'] if term else outgoing['counterparty_id'] if outgoing else '')).fetchone()
            result.append({'id':o['id'],'customer':o['customer'],'country':o['country'],'goods':o['goods'],'currency':o['currency'],
                'total':o['total_minor']/100,'received':o['received_minor']/100,'adjustment':o['adjustment_minor']/100,'status':o['status'],
                'expected':term['expected_minor']/100 if term else (incoming['original_minor'] or incoming['signed_minor'])/100 if incoming else 0,
                'receipt_date':term['receipt_date'] if term else incoming['due_date'] if incoming else None,
                'fx_rate':float(term['fx_rate']) if term else incoming['signed_minor']/incoming['original_minor'] if incoming and incoming['original_minor'] else 1,
                'supplier':supplier[0] if supplier else '', 'supplier_amount':term['supplier_minor']/100 if term else -outgoing['signed_minor']/100 if outgoing else 0,
                'supplier_date':term['supplier_date'] if term else outgoing['due_date'] if outgoing else None})
        return result

    def business_snapshot(self, tenant, db):
        company=db.execute('SELECT * FROM companies WHERE id=?',(tenant,)).fetchone()
        if not company: raise NotFound('Company not found.')
        accounts=[dict(r) for r in db.execute('SELECT * FROM bank_accounts WHERE company_id=?',(tenant,))]
        return {'kind':'business','company_id':tenant,'company_name':company['name'],'version':company['financial_version'],
                'planning_start':company['planning_start'],'opening':sum(a['opening_minor'] for a in accounts if a['currency']=='CNY' and not a['reserved'])/100,
                'accounts':accounts,'orders':self.order_records(tenant,db),
                'movements':[dict(r) for r in db.execute('SELECT * FROM cash_movements WHERE company_id=? ORDER BY due_date,id',(tenant,))]}

    def overview(self, tenant):
        with self.db.connect() as db:
            snapshot=self.business_snapshot(tenant,db)
            return {'company':dict(db.execute('SELECT * FROM companies WHERE id=?',(tenant,)).fetchone()),'snapshot':snapshot,'cash':forecast(snapshot)}

    def record_revision(self, db, tenant, reason, increment=True):
        if increment: db.execute('UPDATE companies SET financial_version=financial_version+1 WHERE id=?',(tenant,))
        snapshot=self.business_snapshot(tenant,db)
        db.execute('INSERT INTO financial_revisions VALUES(?,?,?,?,?)',(tenant,snapshot['version'],json.dumps(snapshot),reason,time.time()))
        return snapshot

    def save_order(self, tenant, body, *, create, preview=False):
        with self.db.connect(write=True) as db:
            company=db.execute('SELECT * FROM companies WHERE id=?',(tenant,)).fetchone()
            if not company: raise NotFound('Company not found.')
            if company['financial_version']!=body.version: raise Conflict('Business data changed. Reload and review this order again.')
            exists=db.execute('SELECT currency,adjustment_minor FROM trade_orders WHERE company_id=? AND id=?',(tenant,body.id)).fetchone()
            if create and exists: raise Conflict('This order number already exists.')
            if not create and not exists: raise NotFound('Order not found.')
            adjustment=exists['adjustment_minor'] if exists else 0
            if adjustment and exists['currency']!=body.currency:
                raise ValueError('An order with recorded adjustments must retain its currency.')
            if minor(body.received+body.expected)+adjustment>minor(body.total):
                raise ValueError('Receipts and recorded adjustments exceed the order value.')
            if any(d and str(d)<company['planning_start'] for d in (body.receipt_date,body.supplier_date)):
                raise ValueError('Future cash dates must be on or after the opening balance date.')
            before=forecast(self.business_snapshot(tenant,db))
            customer='customer:'+body.id;supplier='supplier:'+body.id
            db.execute('INSERT INTO counterparties VALUES(?,?,?,?,?) ON CONFLICT(company_id,id) DO UPDATE SET name=excluded.name,country=excluded.country',(tenant,customer,body.customer,'customer',body.country))
            if body.supplier:
                db.execute('INSERT INTO counterparties VALUES(?,?,?,?,?) ON CONFLICT(company_id,id) DO UPDATE SET name=excluded.name',(tenant,supplier,body.supplier,'supplier','CN'))
            db.execute('INSERT INTO trade_orders VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(company_id,id) DO UPDATE SET customer_id=excluded.customer_id,goods=excluded.goods,currency=excluded.currency,total_minor=excluded.total_minor,received_minor=excluded.received_minor,status=excluded.status',
                (tenant,body.id,customer,body.goods,body.currency,minor(body.total),minor(body.received),adjustment,body.status))
            db.execute('INSERT OR REPLACE INTO order_terms VALUES(?,?,?,?,?,?,?,?)',
                (tenant,body.id,minor(body.expected),str(body.receipt_date) if body.receipt_date else None,str(body.fx_rate),supplier if body.supplier else None,minor(body.supplier_amount),str(body.supplier_date) if body.supplier_date else None))
            db.execute('DELETE FROM cash_movements WHERE company_id=? AND order_id=? AND status!=?',(tenant,body.id,'posted'))
            if body.status not in ('cancelled','completed'):
                if body.expected:
                    db.execute('INSERT INTO cash_movements VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                        (tenant,body.id+':receipt',body.id,customer,'Expected receipt · '+body.id,str(body.receipt_date),'CNY',minor(body.expected*body.fx_rate),'expected',body.currency,minor(body.expected),str(body.fx_rate)))
                if body.supplier_amount:
                    db.execute('INSERT INTO cash_movements VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                        (tenant,body.id+':supplier',body.id,supplier,'Supplier payment · '+body.id,str(body.supplier_date),'CNY',-minor(body.supplier_amount),'obligation',None,None,None))
            after=forecast(self.business_snapshot(tenant,db))
            if preview:
                db.rollback()
                return {'before':before,'after':after,'order':body.model_dump(mode='json')}
            db.execute('INSERT OR IGNORE INTO company_access VALUES(?,?)',(tenant,tenant))
            self.record_revision(db,tenant,'order_created:'+body.id if create else 'order_updated:'+body.id)
        return self.overview(tenant)
