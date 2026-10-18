import test from 'node:test';
import assert from 'node:assert/strict';
import { samplePartialEmail, inspectPaymentEmail, readPaymentDetails, paymentProblem, partialReceipt } from '../src/partial-payment.js';
import { enrich, seriesFor } from '../src/finance.js';

test('an incomplete email preserves unknown payment fields', () => {
  const r = inspectPaymentEmail(samplePartialEmail);
  assert.equal(r.order, 'TF-26104');
  assert.equal(r.partial, true);
  assert.equal(r.amountUSD, null);
  assert.equal(r.date, '');
});

test('invoice totals and header dates are not payment commitments', () => {
  const r = inspectPaymentEmail('Date: 2026-10-18\nSubject: TF-26104\n\nOutstanding invoice: USD 12,000. We will pay the undisputed portion first.');
  assert.equal(r.amountUSD, null);
  assert.equal(r.date, '');
  const explicit = inspectPaymentEmail('TF-26104: We will pay USD 4,500 first on 2026-11-02. Remaining balance follows later.');
  assert.equal(explicit.amountUSD, 4500);
  assert.equal(explicit.date, '2026-11-02');
});

test('separate replies preserve amount while clarifying date', () => {
  const a = readPaymentDetails('6000美元', { reply: true });
  assert.equal(paymentProblem(a), 'dateMissing');
  const d = readPaymentDetails('10月29日', { reply: true });
  const draft = { amountUSD: a.amountUSD, date: d.date };
  assert.equal(paymentProblem(draft), '');
  assert.deepEqual(partialReceipt(draft), { amountUSD: 6000, netCNY: 40000, remainingUSD: 6000 });
  assert.equal(readPaymentDetails('The buyer will pay USD 6,000 first').amountUSD, 6000);
});

test('invalid amounts and dates cannot confirm a partial plan', () => {
  for (const amountUSD of [0, -1, 12000, 13000]) assert.equal(paymentProblem({ amountUSD, date: '2026-10-29' }), 'amountRange');
  assert.equal(paymentProblem({ amountUSD: 6000, date: '' }), 'dateMissing');
  assert.equal(paymentProblem({ amountUSD: 6000, date: '2026-11-31' }), 'dateRange');
  assert.equal(paymentProblem({ amountUSD: 6000, date: '2026-12-12' }), 'dateRange');
});

test('partial forecast replaces full receipt and leaves remainder unscheduled', () => {
  const before = { opening: 128000, supplierDay: 25, receiptDay: 27 };
  const after = { ...before, receiptDay: 12, partialReceipt: partialReceipt({ amountUSD: 6000 }) };
  assert.equal(enrich(before).peak, 74000);
  assert.equal(enrich(after).peak, 34000);
  const points = seriesFor(after);
  assert.equal(points[0].v, 128000);
  assert.equal(points[12].v, 168000);
  assert.equal(points[27].v, -34000);
  assert.equal(after.partialReceipt.remainingUSD, 6000);
  assert.equal(enrich({ ...after, supplierDay: 35 }).peak, 0);
  assert.equal(enrich({ ...after, receiptDay: 26 }).peak, 74000);
});
