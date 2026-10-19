import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {setupDocuments,parseSetupDocument} from '../src/onboarding.js';
import {enrich} from '../src/finance.js';
const records = JSON.parse(readFileSync(new URL('./fixtures/baseline-text.json',import.meta.url),'utf8'));
test('the three uploaded records reconstruct the original cash gap without payment-email assumptions',()=>{
  const cash=parseSetupDocument('cash',records.cash);
  const sales=parseSetupDocument('sales',records.sales);
  const supplier=parseSetupDocument('supplier',records.supplier);
  assert.deepEqual(cash,{opening:128000,usd:19970});
  assert.deepEqual(sales,{order:'TF-26104',outstanding:12000,receiptDay:12});
  assert.deepEqual(supplier,{payable:160000,supplierDay:5});
  const baseline=enrich({...cash,...sales,...supplier});
  assert.equal(baseline.peak,32000); assert.equal(baseline.first,5);
});
test('a wrong file or changed unsupported obligation cannot become a confirmed demo baseline',()=>{
  assert.throws(()=>parseSetupDocument('sales',records.cash),/Missing field/);
  assert.throws(()=>parseSetupDocument('supplier',records.supplier.replace('160,000','180,000')),/TF-26104 supplier/);
  assert.throws(()=>parseSetupDocument('cash',records.cash.replace('42,000','24,000')),/cash schedule/);
});
