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

export function seriesFor(s) {
  let v = s.opening;
  return Array.from({ length: 56 }, (_, d) => {
    if (d === s.supplierDay) v -= 160000;
    if (d === s.receiptDay) v += receiptCNY(s);
    if (d === 20) v -= 42000;
    if (d === 30) v += 120000;
    if (d === 40) v -= 38000;
    if (d === 50) v += 65000;
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
