import { dayNumber } from './finance.js';

export const samplePartialEmail = `From: accounts@harbour.example
Subject: Partial payment for TF-26104

Dear StarSail team,

Some items in order TF-26104 are under quality review. We will pay the undisputed portion first. The remaining balance will be settled once the review is complete.

Please coordinate with our accounts team on the payment arrangements.

Best regards,
Harbour Supplies`;

// This local demo recognizes explicit payment wording; it does not call an LLM.
export function readPaymentDetails(text, { reply = false } = {}) {
  let amount = text.match(/(?:先付|先支付|本次支付|部分付款|pay(?:ment)?(?:\s+of)?|first\s+payment(?:\s+of)?)\s*[:：]?\s*(?:USD|US\$|\$)\s*([\d,]+(?:\.\d{1,2})?)/i)
    || text.match(/(?:先付|先支付|本次支付)\s*([\d,]+(?:\.\d{1,2})?)\s*美元/i)
    || text.match(/^(?:USD|US\$|\$)\s*([\d,]+(?:\.\d{1,2})?)/i);
  if (!amount && reply) amount = text.match(/(?:USD|US\$|\$)\s*([\d,]+(?:\.\d{1,2})?)/i)
    || text.match(/([\d,]+(?:\.\d{1,2})?)\s*美元/)
    || text.trim().match(/^([\d,]+(?:\.\d{1,2})?)$/);
  const iso = text.match(/\b(2026-\d{2}-\d{2})\b/);
  const chinese = text.match(/(\d{1,2})月(\d{1,2})[日号]?/);
  return {
    amountUSD: amount ? Number(amount[1].replaceAll(',', '')) : null,
    date: iso?.[1] || (chinese ? `2026-${chinese[1].padStart(2,'0')}-${chinese[2].padStart(2,'0')}` : ''),
  };
}

export function inspectPaymentEmail(text) {
  const body = text.replace(/^(?:From|To|Date|Subject|Content-Type|MIME-Version):[^\n]*$/gmi, '').trim();
  const order = text.match(/TF-\d{5}/i)?.[0].toUpperCase() || '';
  const partial = /部分|先付|先支付|undisputed|partial|remaining balance/i.test(body);
  return { order, partial, disputed: /quality|disput|质量|争议/i.test(body), ...readPaymentDetails(body) };
}

export function paymentProblem(draft) {
  if (draft.amountUSD === null || draft.amountUSD === '') return 'amountMissing';
  if (!(Number(draft.amountUSD) > 0 && Number(draft.amountUSD) < 12000)) return 'amountRange';
  if (!draft.date) return 'dateMissing';
  const day = dayNumber(draft.date);
  if (!Number.isInteger(day) || day < 0 || day > 55 || new Date(draft.date + 'T00:00:00Z').toISOString().slice(0,10) !== draft.date) return 'dateRange';
  return '';
}

export function partialReceipt(draft) {
  const amountUSD = Number(draft.amountUSD);
  return { amountUSD, netCNY: Math.round(amountUSD / 12000 * 80000 * 100) / 100, remainingUSD: 12000 - amountUSD };
}
