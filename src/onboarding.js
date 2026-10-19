import { dayNumber } from './finance.js';

export const setupDocuments = [
  { id: 'cash', file: '01_company_cash_schedule.txt', label: ['企业资金表', 'Company cash schedule'], purpose: ['建立期初余额与其他经营收支。', 'Establish opening balances and operating cash movements.'] },
  { id: 'sales', file: '02_sales_order_TF-26104.txt', label: ['销售订单', 'Sales order'], purpose: ['建立客户、订单与待收款。', 'Create the buyer, order and outstanding receipt.'] },
  { id: 'supplier', file: '03_supplier_payment_terms_TF-26104.txt', label: ['供应商付款条款', 'Supplier payment terms'], purpose: ['关联采购款金额与到期日。', 'Link the supplier obligation and payment date.'] },
];
const number = value => Number(value.replaceAll(',', ''));
const read = (text, pattern, field) => {
  const match = text.match(pattern);
  if (!match) throw Error(`Missing field: ${field}`);
  return match[1].trim();
};
const calendarDay = value => {
  const date = new Date(value + ' 00:00:00 UTC');
  if (Number.isNaN(date.valueOf())) throw Error('Use an English calendar date, for example 22 October 2026.');
  const day = dayNumber(date.toISOString().slice(0, 10));
  if (day < 0 || day > 55) throw Error('The date must be within the 56-day demo period.');
  return day;
};

// Import the supplied case's documented text format, independently of the LLM.
export function parseSetupDocument(kind, text) {
  if (kind === 'cash') {
    const opening = number(read(text, /CNY operating account available balance: ([\d,]+)/, 'CNY opening balance'));
    const usd = number(read(text, /USD bank account balance displayed separately: ([\d,]+)/, 'USD balance'));
    const schedule = [[6, 'November', 'outflow', '42,000'], [16, 'November', 'inflow', '120,000'], [26, 'November', 'outflow', '38,000'], [6, 'December', 'inflow', '65,000']];
    for (const [day, month, direction, amount] of schedule) {
      if (!text.includes(`${day} ${month} 2026:`) || !new RegExp(`${day} ${month} 2026:[^\\n]*${direction} ${amount.replace(',', ',?')}`).test(text)) throw Error('The cash schedule does not match this demonstration case.');
    }
    if (usd !== 19970 || !text.includes('CNY 80,000 net proceeds')) throw Error('Use the supplied cash schedule for this demonstration.');
    return { opening, usd };
  }
  if (kind === 'sales') {
    const order = read(text, /^Order: (.+)$/m, 'Order ID');
    const outstanding = number(read(text, /Outstanding balance: USD ([\d,]+)/, 'Outstanding balance'));
    if (order !== 'TF-26104' || outstanding !== 12000 || !text.includes('Harbour Supplies')) throw Error('Use the TF-26104 sales order for this demonstration.');
    const receiptDay = calendarDay(read(text, /Original planned balance settlement and CNY availability: ([^.]+)/, 'Receipt date'));
    return { order, outstanding, receiptDay };
  }
  const payable = number(read(text, /Outstanding procurement payable: CNY ([\d,]+)/, 'Supplier amount'));
  if (payable !== 160000 || !text.includes('Linked export order: TF-26104')) throw Error('Use the TF-26104 supplier terms for this demonstration.');
  return { payable, supplierDay: calendarDay(read(text, /Agreed payment date: ([^\n]+)/, 'Supplier date')) };
}
