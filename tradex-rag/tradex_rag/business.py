"""Relational business records and the existing demo UI's persistence adapter."""
import json
import time
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from .service import Conflict

START = date(2026, 10, 17)
FIELDS = ('version', 'opening', 'supplierDay', 'receiptDay', 'amountUSD')

def minor(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def day(value):
    return (date.fromisoformat(value) - START).days

from .business_records import BusinessRecords

class BusinessStore(BusinessRecords):
    def __init__(self, db):
        self.db = db
        with db.connect(write=True) as conn:
            conn.executescript(Path(__file__).with_name('sql').joinpath('business.sql').read_text())
            # Existing accepted forecasts are migrated once; original agent records stay intact.
            for row in conn.execute('SELECT tenant,snapshot FROM agent_workspaces').fetchall():
                if not conn.execute('SELECT 1 FROM companies WHERE id=?', (row['tenant'],)).fetchone():
                    self.write_snapshot(conn, row['tenant'], json.loads(row['snapshot']), 'legacy_migration')

    def ensure_company(self, db, tenant):
        db.execute('INSERT OR IGNORE INTO companies VALUES(?,?,?,?,?,?,?)',
                   (tenant, 'StarSail Exports', 'CN', 'CNY', str(START), 0, time.time()))

    def seed_case(self, db, tenant):
        self.ensure_company(db, tenant)
        if db.execute('SELECT 1 FROM trade_orders WHERE company_id=? AND id=?', (tenant,'TF-26104')).fetchone(): return
        db.executemany('INSERT INTO counterparties VALUES(?,?,?,?,?)', [
            (tenant,'harbour','Harbour Supplies','customer','GB'),
            (tenant,'papercraft','Dongguan PaperCraft Manufacturing','supplier','CN')])
        db.execute('INSERT INTO trade_orders VALUES(?,?,?,?,?,?,?,?,?)',
                   (tenant,'TF-26104','harbour','Stationery sets','USD',4000000,2800000,0,'preparing'))
        db.executemany('INSERT INTO bank_accounts VALUES(?,?,?,?,?,?,?)', [
            (tenant,'cny-operating','CNY operating account','CNY',0,str(START),0),
            (tenant,'usd-reserved','USD account','USD',1997000,str(START),1)])
        rows = [
            ('supplier','TF-26104','papercraft','Supplier payment',5,-16000000,'obligation',None,None,None),
            ('receipt','TF-26104','harbour','Expected receipt conversion',12,8000000,'expected','USD',1200000,'CNY 80000 per USD 12000; fixed demo assumption'),
            ('operating',None,None,'Logistics & operating costs',20,-4200000,'obligation',None,None,None),
            ('other-receipt',None,None,'Other expected receipts',30,12000000,'expected',None,None,None),
            ('other-payment',None,None,'Other operating payments',40,-3800000,'obligation',None,None,None),
            ('later-receipt',None,None,'Other expected receipts',50,6500000,'expected',None,None,None)]
        db.executemany('INSERT INTO cash_movements VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', [
            (tenant, ident, order, party, label, str(START+timedelta(days=due)), 'CNY', amount, status, currency, original, basis)
            for ident,order,party,label,due,amount,status,currency,original,basis in rows])

    def snapshot(self, tenant, db=None):
        if db is None:
            with self.db.connect() as conn: return self.snapshot(tenant, conn)
        if self.is_managed(tenant, db): return self.business_snapshot(tenant,db)
        company=db.execute('SELECT financial_version FROM companies WHERE id=?', (tenant,)).fetchone()
        if not company or not company['financial_version']: return None
        opening=db.execute("SELECT opening_minor FROM bank_accounts WHERE company_id=? AND id='cny-operating'", (tenant,)).fetchone()[0]
        movements={r['id']: dict(r) for r in db.execute('SELECT * FROM cash_movements WHERE company_id=? ORDER BY due_date,id', (tenant,))}
        return {'version':company['financial_version'], 'opening':opening/100,
                'supplierDay':day(movements['supplier']['due_date']), 'receiptDay':day(movements['receipt']['due_date']),
                'amountUSD':movements['receipt']['original_minor']/100,
                'movements':list(movements.values())}

    def write_snapshot(self, db, tenant, snapshot, reason):
        if self.is_managed(tenant,db): raise Conflict('Use order confirmation to update this company.')
        self.seed_case(db, tenant)
        old=self.snapshot(tenant, db)
        if old and snapshot['version'] <= old['version']:
            if snapshot['version'] == old['version'] and any(snapshot[k] != old[k] for k in FIELDS):
                raise Conflict('Financial version changed in another page. Reload the workspace before saving.')
            return old
        amount=minor(snapshot['amountUSD'])
        net=int((Decimal(amount)*Decimal(80000)/Decimal(12000)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        db.execute("UPDATE bank_accounts SET opening_minor=? WHERE company_id=? AND id='cny-operating'", (minor(snapshot['opening']),tenant))
        db.execute("UPDATE cash_movements SET due_date=? WHERE company_id=? AND id='supplier'", (str(START+timedelta(days=snapshot['supplierDay'])),tenant))
        db.execute("UPDATE cash_movements SET due_date=?,signed_minor=?,original_minor=? WHERE company_id=? AND id='receipt'", (str(START+timedelta(days=snapshot['receiptDay'])),net,amount,tenant))
        db.execute('UPDATE companies SET financial_version=? WHERE id=?', (snapshot['version'],tenant))
        clean={k:snapshot[k] for k in FIELDS}
        db.execute('INSERT INTO financial_revisions VALUES(?,?,?,?,?)', (tenant,snapshot['version'],json.dumps(clean),reason,time.time()))
        # Keep a compatibility snapshot for existing run/proposal records in the same transaction.
        db.execute('INSERT OR REPLACE INTO agent_workspaces VALUES(?,?,?)', (tenant,snapshot['version'],json.dumps(clean)))
        return self.snapshot(tenant,db)

    def records(self, tenant, db=None):
        if db is None:
            with self.db.connect() as conn: return self.records(tenant, conn)
        result={}
        row=db.execute('SELECT * FROM companies WHERE id=?',(tenant,)).fetchone()
        result['company']=dict(row) if row else None
        for name in ('counterparties','bank_accounts','trade_orders','cash_movements','business_evidence'):
            result[name]=[dict(r) for r in db.execute(f'SELECT * FROM {name} WHERE company_id=?',(tenant,))]
        result['financial']=self.snapshot(tenant,db)
        return result

    def view(self, tenant, key, db=None):
        if db is None:
            with self.db.connect() as conn: return self.view(tenant,key,conn)
        row=db.execute('SELECT * FROM workspace_views WHERE company_id=? AND view_key=?',(tenant,key)).fetchone()
        payload=json.loads(row['payload']) if row else None
        snapshot=self.snapshot(tenant,db)
        if payload and snapshot and (not payload['flow'].get('setup') or payload['flow']['setup'].get('complete')):
            flow=payload['flow'];flow.update({k:snapshot[k] for k in ('version','opening','supplierDay','receiptDay')})
            amount=snapshot['amountUSD']
            flow['partialReceipt']={'amountUSD':amount,'netCNY':next(m['signed_minor']/100 for m in snapshot['movements'] if m['id']=='receipt'),'remainingUSD':12000-amount} if amount < 12000 else None
            flow['movements']=snapshot['movements']
            fee=db.execute("SELECT total_minor-received_minor-adjustment_minor FROM trade_orders WHERE company_id=? AND id='TF-26091'",(tenant,)).fetchone()
            if fee: flow['feeRemaining']=fee[0]/100
        return {'revision':row['revision'] if row else 0, 'workspace':payload, 'financial':snapshot, 'business':self.records(tenant,db)}

    def save_view(self, tenant, key, revision, payload):
        payload=deepcopy(payload)
        with self.db.connect(write=True) as db:
            self.ensure_company(db,tenant)
            row=db.execute('SELECT revision FROM workspace_views WHERE company_id=? AND view_key=?',(tenant,key)).fetchone()
            if revision != (row['revision'] if row else 0): raise Conflict('Workspace updated in another browser. Reload before saving.')
            flow=payload['flow']; setup=flow.get('setup')
            if not setup or setup.get('complete'):
                snapshot={k:flow[k] for k in ('version','opening','supplierDay','receiptDay')}
                snapshot['amountUSD']=(flow.get('partialReceipt') or {}).get('amountUSD',12000)
                self.write_snapshot(db,tenant,snapshot,'confirmed_workspace')
                if not setup:
                    db.execute('INSERT OR IGNORE INTO counterparties VALUES(?,?,?,?,?)',(tenant,'nordlicht','Nordlicht GmbH','customer','DE'))
                    db.execute('INSERT OR IGNORE INTO trade_orders VALUES(?,?,?,?,?,?,?,?,?)',(tenant,'TF-26091','nordlicht','LED lamps','USD',2000000,1997000,0,'shipped'))
                    db.execute("UPDATE trade_orders SET adjustment_minor=? WHERE company_id=? AND id='TF-26091'", (minor(30-flow.get('feeRemaining',30)),tenant))
                for kind,record in (setup or {}).get('records',{}).items():
                    db.execute('INSERT OR REPLACE INTO business_evidence VALUES(?,?,?,?,?)',(tenant,record['documentId'],record.get('version',1),None if kind=='cash' else 'TF-26104',kind))
            for field in ('version','opening','supplierDay','receiptDay','partialReceipt','movements','feeRemaining'):
                if not setup or setup.get('complete'): flow.pop(field,None)
            db.execute('INSERT OR REPLACE INTO workspace_views VALUES(?,?,?,?,?)',(tenant,key,revision+1,json.dumps(payload,ensure_ascii=False),time.time()))
            return self.view(tenant,key,db)
