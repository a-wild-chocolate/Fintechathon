import test from 'node:test';
import assert from 'node:assert/strict';
import { cashEvents, seriesFor } from '../src/finance.js';
import { cashAnalysisQuestion } from '../src/cash-chart.js';

const base = { opening: 128000, supplierDay: 5, receiptDay: 12 };

test('saved company movements use their own dates, units and order IDs', () => {
  const snapshot = {kind:'business', planning_start:'2027-02-01', opening:50000, movements:[
    {id:'NEW-2:supplier',order_id:'NEW-2',due_date:'2027-02-05',signed_minor:-3000000,status:'obligation',label:'Supplier payment · NEW-2'},
    {id:'NEW-2:receipt',order_id:'NEW-2',due_date:'2027-02-15',signed_minor:4000000,status:'expected',label:'Expected receipt · NEW-2'},
    {id:'historic',order_id:'NEW-2',due_date:'2027-02-01',signed_minor:1000000,status:'posted',label:'Historical receipt'},
  ]};
  const events = cashEvents(snapshot);
  assert.deepEqual(events.map(e=>[e.orderId,e.day,e.amount]),[['NEW-2',4,-30000],['NEW-2',14,40000]]);
  assert.match(events[0].label[0], /供应商付款/);
  const series = seriesFor(snapshot);
  assert.equal(series[0].v,50000);
  assert.equal(series[4].v,20000);
  assert.equal(series[14].v,60000);
});

test('every chart jump equals its listed cash movements, including shared dates', () => {
  const snapshot = { ...base, supplierDay: 12 };
  const points = seriesFor(snapshot);
  const events = cashEvents(snapshot);
  for (const { d, v } of points) {
    const previous = d ? points[d - 1].v : snapshot.opening;
    assert.equal(v - previous, events.filter(event => event.day === d).reduce((sum, event) => sum + event.amount, 0));
  }
  assert.equal(points[12].v, 48000);
  assert.equal(events.filter(event => event.day === 12).length, 2);
});

test('partial receipts and rescheduled payments keep their real order association', () => {
  const events = cashEvents({ ...base, supplierDay: 25, partialReceipt: { netCNY: 40000 } });
  assert.equal(events.find(event => event.id === 'supplier').day, 25);
  assert.equal(events.find(event => event.id === 'receipt').amount, 40000);
  assert.deepEqual(events.filter(event => event.orderId).map(event => event.orderId), ['TF-26104', 'TF-26104']);
  assert.equal(events.find(event => event.id === 'operating').orderId, null);
});

test('AI question carries the selected movement and chart scenario in both languages', () => {
  const snapshot = { ...base, supplierDay: 15 };
  const event = cashEvents(snapshot).find(event => event.id === 'supplier');
  for (const lang of ['en', 'zh']) {
    const question = cashAnalysisQuestion(event, snapshot, lang);
    assert.match(question, /TF-26104/);
    assert.match(question, /2026-11-01/);
    assert.match(question, /2026-10-29/);
    assert.match(question, /−¥160,000/);
  }
  assert.match(cashAnalysisQuestion(event, snapshot, 'en'), /keep the ledger unchanged/);
});
