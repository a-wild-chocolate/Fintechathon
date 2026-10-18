import test from 'node:test';
import assert from 'node:assert/strict';
import { followupView } from '../src/followups.js';
const base = { version:1, opening:128000, supplierDay:5, receiptDay:12, jobs:[] };
test('supplier reminder fires three days before payment and evaluates actual schedule',()=>{
  assert.equal(followupView(base,{day:1}).items.some(x=>x.kind==='supplier'),false);
  const alert=followupView(base,{day:2}).items.find(x=>x.kind==='supplier');
  assert.equal(alert.gap,32000);
  assert.equal(followupView({...base,opening:200000},{day:2}).items.some(x=>x.kind==='supplier'),false);
});
test('confirmed extension replaces the old timer and cancels an obsolete gap',()=>{
  const revised={...base,version:2,supplierDay:15};
  assert.equal(followupView(revised,{day:2}).watches[0].day,12);
  assert.equal(followupView(revised,{day:2}).items.some(x=>x.kind==='supplier'),false);
  assert.equal(followupView(revised,{day:12}).items.some(x=>x.kind==='supplier'),false);
});
test('reading and repeated evaluation do not create duplicate unread alerts',()=>{
  const first=followupView(base,{day:2});
  const read=first.items.map(x=>x.id);
  assert.equal(followupView(base,{day:2,read}).items.filter(x=>x.unread).length,0);
  assert.deepEqual(followupView(base,{day:2}).items.map(x=>x.id),read);
});
test('receipt date requests verification and respects paused follow-ups',()=>{
  assert.equal(followupView(base,{day:11}).items.some(x=>x.kind==='receipt'),false);
  assert.equal(followupView(base,{day:12}).items.some(x=>x.kind==='receipt'),true);
  assert.equal(followupView(base,{day:12,paused:['receipt']}).items.some(x=>x.kind==='receipt'),false);
});
test('confirmation replaces missing-evidence alert with a state update',()=>{
  const job={id:'mail-1',scope:'buyer',status:'clarifying'};
  assert.equal(followupView({...base,jobs:[job]}).items.some(x=>x.kind==='evidence'),true);
  const accepted={...base,version:2,jobs:[{...job,status:'confirmed',after:{v:2}}],partialReceipt:{amountUSD:6000,netCNY:40000,remainingUSD:6000}};
  const view=followupView(accepted);
  assert.equal(view.items.some(x=>x.kind==='evidence'),false);
  assert.equal(view.items.find(x=>x.kind==='updated').peak,34000);
  assert.equal(accepted.opening,128000);
});
