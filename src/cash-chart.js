import { cashEvents, isoDay, money, receiptCNY } from './finance.js';

const signed = value => `${value < 0 ? '−' : '+'}${money(value)}`;

export function cashAnalysisQuestion(event, snapshot, language) {
  const amount = signed(event.amount);
  return language === 'en'
    ? `Analyze the cash impact of ${event.orderId || 'company cash'}: ${event.label[1]}, ${isoDay(event.day)}, ${amount}. Chart scenario: opening CNY ${snapshot.opening}; supplier CNY 160000 on ${isoDay(snapshot.supplierDay)}; expected net receipt CNY ${receiptCNY(snapshot)} on ${isoDay(snapshot.receiptDay)}. Explain the shortfall and next action; keep the ledger unchanged.`
    : `分析${event.orderId || '企业资金'}的资金影响：${event.label[0]}，${isoDay(event.day)}，${amount}。图中情景：期初人民币${snapshot.opening}；供应商付款160000元，日期${isoDay(snapshot.supplierDay)}；预计结汇净额${receiptCNY(snapshot)}元，日期${isoDay(snapshot.receiptDay)}。解释资金缺口和下一步建议，不修改账本。`;
}

export function attachCashChart(svg, { snapshot, points, baseline, comparisonLabel, language, x, y, width, height, onSelect }) {
  const en = language === 'en';
  const events = cashEvents(snapshot).filter(event => event.day >= 0 && event.day < points.length);
  const host = document.createElement('div');
  host.className = 'cash-chart-interactive';
  svg.replaceWith(host);
  host.append(svg);
  svg.setAttribute('role', 'group');
  const popover = document.createElement('div');
  popover.className = 'cash-chart-tooltip';
  popover.hidden = true;
  host.append(popover);
  const hint = document.createElement('p');
  hint.className = 'cash-chart-hint';
  hint.textContent = en ? 'Hover to inspect · Select a cash movement to continue' : '悬停查看明细 · 选择收支继续处理';
  host.append(hint);
  svg.insertAdjacentHTML('beforeend', `<g class="cash-chart-cursor" visibility="hidden" pointer-events="none"><line y1="19" y2="${height - 30}"/><circle r="4"/></g>${[...new Set(events.map(event => event.day))].map(day => `<g class="cash-chart-point" tabindex="0" role="button" data-day="${day}" aria-label="${isoDay(day)} · ${events.filter(event => event.day === day).map(event => `${event.label[en ? 1 : 0]} ${signed(event.amount)}`).join('; ')}"><circle cx="${x(day)}" cy="${y(points[day].v)}" r="13" fill="transparent"/><circle cx="${x(day)}" cy="${y(points[day].v)}" r="3.5" class="cash-chart-dot"/></g>`).join('')}`);
  const cursor = svg.querySelector('.cash-chart-cursor');
  let pinned = false;
  const hide = () => { popover.hidden = true; cursor.setAttribute('visibility', 'hidden'); pinned = false; };
  const show = day => {
    const movements = events.filter(event => event.day === day);
    const balance = points[day].v;
    const prior = baseline[day].v;
    popover.innerHTML = `<strong>${isoDay(day)}</strong><div class="cash-chart-balance"><span>${en ? 'Projected closing balance' : '预计日末余额'}</span><b>${balance < 0 ? '−' : ''}${money(balance)}</b></div>${prior !== balance ? `<small>${comparisonLabel}: ${prior < 0 ? '−' : ''}${money(prior)}</small>` : ''}<ul>${movements.map(event => `<li><span>${event.label[en ? 1 : 0]}<small>${event.orderId || (en ? 'Company cash' : '企业资金')}</small></span><b>${signed(event.amount)}</b></li>`).join('')}</ul>${movements.length ? movements.map(event => `<button type="button" data-cash-event="${event.id}">${event.orderId ? `${event.orderId} · ${en ? 'View order' : '查看订单'}` : en ? 'Analyze company cash' : '分析企业资金'} →</button>`).join('') : `<small>${en ? 'No scheduled cash movements on this day.' : '当日无计划收支。'}</small>`}`;
    popover.hidden = false;
    popover.style.left = `${Math.max(0, Math.min(x(day) - popover.offsetWidth / 2, width - popover.offsetWidth))}px`;
    popover.style.top = `${Math.min(y(balance), height - 30) + 16}px`;
    cursor.setAttribute('visibility', 'visible');
    const line = cursor.querySelector('line');
    line.setAttribute('x1', x(day)); line.setAttribute('x2', x(day));
    const dot = cursor.querySelector('circle');
    dot.setAttribute('cx', x(day)); dot.setAttribute('cy', y(balance));
  };
  const dayAt = event => Math.max(0, Math.min(55, Math.round((event.clientX - svg.getBoundingClientRect().left - x(0)) / (x(55) - x(0)) * 55)));
  svg.addEventListener('pointermove', event => { if (!pinned && event.pointerType !== 'touch') show(dayAt(event)); });
  svg.addEventListener('click', event => {
    const day = Number(event.target.closest('[data-day]')?.dataset.day ?? dayAt(event));
    const movements = events.filter(item => item.day === day);
    if (movements.length === 1) onSelect(movements[0], snapshot);
    else { pinned = true; show(day); }
  });
  svg.addEventListener('focusin', event => { if (event.target.matches('[data-day]')) { pinned = true; show(Number(event.target.dataset.day)); } });
  svg.addEventListener('keydown', event => {
    if (event.key === 'Escape') hide();
    if (['Enter', ' '].includes(event.key) && event.target.matches('[data-day]')) {
      event.preventDefault(); pinned = true; show(Number(event.target.dataset.day)); popover.querySelector('button')?.focus();
    }
  });
  host.addEventListener('pointerleave', () => { if (!pinned) hide(); });
  host.addEventListener('keydown', event => { if (event.key === 'Escape') hide(); });
  host.addEventListener('focusout', event => { if (!host.contains(event.relatedTarget)) hide(); });
  popover.addEventListener('click', event => {
    const button = event.target.closest('[data-cash-event]');
    if (button) onSelect(events.find(item => item.id === button.dataset.cashEvent), snapshot);
  });
}
