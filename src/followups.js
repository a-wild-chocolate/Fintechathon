import { enrich, seriesFor } from './finance.js';

// Local demo: rules read accepted state, never a temporary cash scenario.
export function followupView(flow, { day = 0, paused = [], read = [] } = {}) {
  const cash = enrich(flow);
  const pending = flow.jobs.find(j => j.scope === 'buyer' && j.status !== 'confirmed');
  const latest = flow.jobs.find(j => j.scope === 'buyer' && j.status === 'confirmed' && j.after?.v === flow.version);
  const watches = [
    { id: 'supplier', day: Math.max(0, flow.supplierDay - 3), due: flow.supplierDay },
    { id: 'receipt', day: flow.receiptDay, due: flow.receiptDay },
  ].map(w => ({ ...w, paused: paused.includes(w.id) }));
  const items = [];
  const add = (id, kind, trigger, extra = {}) => items.push({ id, kind, trigger, version: flow.version, ...extra, unread: !read.includes(id) });
  if (pending) add(`evidence-${pending.id}-${pending.status}`, 'evidence', 'event', { job: pending.id });
  if (latest) add(`updated-${flow.version}`, 'updated', 'event', { job: latest.id, peak: cash.peak });
  else if (cash.peak > 0) add(`cash-${flow.version}`, 'cash', 'event', { peak: cash.peak, first: cash.first });
  const dueBalance = seriesFor(flow)[flow.supplierDay].v;
  if (!paused.includes('supplier') && day >= Math.max(0, flow.supplierDay - 3) && day <= flow.supplierDay && dueBalance < 0) {
    add(`supplier-${flow.supplierDay}-${flow.version}`, 'supplier', 'time', { due: flow.supplierDay, gap: -dueBalance });
  }
  if (!paused.includes('receipt') && day >= flow.receiptDay) {
    add(`receipt-${flow.receiptDay}-${flow.version}`, 'receipt', 'time', { due: flow.receiptDay });
  }
  return { items: items.reverse(), watches, next: watches.filter(w => !w.paused && w.day > day).sort((a,b) => a.day-b.day)[0]?.day };
}
