export const money = (n) => "¥" + Math.abs(n).toLocaleString("en-US");

export const date = (d) => {
  let x = new Date(Date.UTC(2026, 9, 17 + d));
  return x.getUTCMonth() + 1 + "/" + x.getUTCDate();
};

export const isoDay = (d) =>
  new Date(Date.UTC(2026, 9, 17 + d)).toISOString().slice(0, 10);

export const dayNumber = (s) =>
  Math.round((Date.parse(s + "T00:00:00Z") - Date.UTC(2026, 9, 17)) / 86400000);

export const receiptCNY = (s) => s.partialReceipt ? s.partialReceipt.netCNY : 80000;

export function cashEvents(s) {
  return [
    { id: "supplier", day: s.supplierDay, amount: -160000, orderId: "TF-26104", label: ["供应商付款", "Supplier payment"] },
    { id: "receipt", day: s.receiptDay, amount: receiptCNY(s), orderId: "TF-26104", label: s.partialReceipt ? ["部分付款预计结汇", "Partial receipt conversion"] : ["预计尾款结汇", "Expected receipt conversion"] },
    { id: "operating", day: 20, amount: -42000, orderId: null, label: ["物流及经营支出", "Logistics & operating costs"] },
    { id: "other-receipt", day: 30, amount: 120000, orderId: null, label: ["其他预计回款", "Other expected receipts"] },
    { id: "other-payment", day: 40, amount: -38000, orderId: null, label: ["其他经营付款", "Other operating payments"] },
    { id: "later-receipt", day: 50, amount: 65000, orderId: null, label: ["其他预计回款", "Other expected receipts"] },
  ].sort((a, b) => a.day - b.day);
}

export function seriesFor(s) {
  const events = cashEvents(s);
  let v = s.opening;
  return Array.from({ length: 56 }, (_, d) => {
    v += events.filter(event => event.day === d).reduce((sum, event) => sum + event.amount, 0);
    return { d, v };
  });
}

export function enrich(s) {
  const a = seriesFor(s),
    f = a.find((x) => x.v < 0);
  return {
    ...s,
    peak: Math.max(0, -Math.min(...a.map((x) => x.v))),
    first: f?.d ?? null,
    gap: f ? -f.v : 0,
  };
}
