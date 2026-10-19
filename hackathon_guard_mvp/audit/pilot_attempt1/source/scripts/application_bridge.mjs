import { readFileSync } from 'node:fs';
import { enrich, seriesFor } from '../../src/finance.js';
import { followupView } from '../../src/followups.js';
import { inspectPaymentEmail, partialReceipt, paymentProblem } from '../../src/partial-payment.js';
const { function: fn, payload } = JSON.parse(readFileSync(0, 'utf8'));
const allowed = { enrich, seriesFor, inspectPaymentEmail, partialReceipt, paymentProblem,
  followupView: p => followupView(p.flow, { day: p.day }) };
if (!Object.hasOwn(allowed, fn)) throw new Error('Function not allowed');
process.stdout.write(JSON.stringify(allowed[fn](payload)));
