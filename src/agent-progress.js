const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const roles = {
  coordinator: ['主助手', 'Coordinator', '理解问题，组织分析', 'Understanding the request and coordinating analysis'],
  reconciliation: ['对账 Agent', 'Reconciliation', '核对资料，识别缺失字段', 'Reviewing evidence and missing payment details'],
  cash_flow: ['现金流 Agent', 'Cash flow', '分析收付款与资金缺口', 'Analyzing receipts, payments and cash gaps'],
  decision: ['决策 Agent', 'Decision', '比较可行方案与下一步', 'Comparing options and next steps'],
};
const operations = {
  wf_status: ['读取订单与资金状态', 'Reading order and cash state'],
  kb_search: ['检索相关资料与政策', 'Searching documents and policies'],
  evidence_read: ['阅读原始文件与条款', 'Reading source documents and terms'],
  wf_reconcile: ['整理付款字段与待确认事项', 'Preparing payment fields and clarification'],
  wf_cash: ['计算现金流与资金缺口', 'Calculating cash flow and shortfalls'],
  wf_options: ['计算并比较付款方案', 'Calculating and comparing payment options'],
  wf_draft: ['准备行动草稿', 'Preparing an action draft'],
  wf_financing: ['查找融资材料要求', 'Finding financing document requirements'],
  task: ['分派任务，等待专业 Agent', 'Delegating to a specialist'],
  web_search: ['检索公开政策与要求', 'Searching public policies and requirements'],
  web_fetch: ['阅读网页并保存引用', 'Reading a public source'],
  sandbox_python: ['在沙盒中处理数据', 'Analyzing data in the sandbox'],
  wf_dispatch: ['分派任务，等待专业 Agent', 'Delegating to a specialist'],
  finish: ['整理分析结果', 'Preparing the response'],
};
const statuses = {
  completed: ['分析完成', 'Analysis complete'], needs_information: ['等待补充信息', 'Waiting for information'],
  needs_approval: ['等待确认方案', 'Waiting for confirmation'], failed: ['分析未完成', 'Analysis incomplete'],
  interrupted: ['分析已中断', 'Analysis interrupted'],
};

export function progressState(trace = [], status = 'running') {
  const steps = [], agents = {};
  for (const e of trace) {
    if (e.event === 'agent_started') agents[e.agent] = 'working';
    if (e.event === 'agent_finished') agents[e.agent] = 'done';
    if (e.event === 'model_started' || e.event === 'tool_started') {
      steps.push({agent:e.agent, tool:e.tool, kind:e.event === 'model_started' ? 'model' : 'tool', status:'working'});
    }
    if (['model_call','tool_result','tool_error'].includes(e.event)) {
      const kind = e.event === 'model_call' ? 'model' : 'tool';
      const step = [...steps].reverse().find(s => s.status === 'working' && s.agent === e.agent && s.kind === kind && (kind === 'model' || s.tool === e.tool));
      if (step) step.status = e.event === 'tool_error' ? 'error' : 'done';
      else if (kind === 'tool') steps.push({agent:e.agent,tool:e.tool,kind,status:e.event === 'tool_error' ? 'error' : 'done'});
    }
  }
  if (status !== 'running') {
    for (const step of steps) if (step.status === 'working') step.status = 'stopped';
    for (const role of Object.keys(agents)) if (agents[role] === 'working') agents[role] = 'stopped';
  }
  const active = [...steps].reverse().find(s => s.status === 'working');
  return {steps, agents, active};
}

export function renderAgentProgress(run = {}, lang = 'zh', expanded = false) {
  const en = lang === 'en', i = en ? 1 : 0;
  const status = run.status || 'running';
  const {steps, active} = progressState(run.trace, status);
  const name = role => (roles[role] || ['助手','Assistant'])[i];
  const label = step => step.kind === 'model' ? (roles[step.agent] || ['','','正在分析','Analyzing'])[i+2] : (operations[step.tool] || ['执行工作流','Running a workflow'])[i];
  const running = status === 'running';
  const title = running ? (active ? `${name(active.agent)} · ${en ? 'Working' : '处理中'}` : (en ? 'Starting analysis' : '正在启动分析')) : (statuses[status] || statuses.failed)[i];
  const subtitle = running ? (active ? label(active) : (en ? 'Connecting to the agent workflow…' : '正在连接 Agent 工作流…')) : (en ? 'Your execution record is available below.' : '可展开查看本次执行过程。');
  const rows = items => items.map(step => `<li class="kb-progress-step ${step.status}"><span class="kb-step-mark" aria-hidden="true">${step.status === 'done' ? '✓' : step.status === 'working' ? '·' : '!'}</span><div><strong>${esc(name(step.agent))}</strong><span>${esc(label(step))}</span></div><small>${({done:['已完成','Done'],working:['进行中','Working'],error:['未成功','Failed'],stopped:['已停止','Stopped']}[step.status])[i]}</small></li>`).join('');
  return `<details class="kb-progress" ${expanded ? 'open' : ''} aria-label="${en ? 'Agent activity' : '智能体执行进度'}"><summary class="kb-progress-head"><span class="kb-progress-indicator ${running ? 'running' : ''}" aria-hidden="true"></span><span class="kb-progress-heading"><strong class="kb-current-agent">${esc(title)}</strong><span class="kb-current-action" role="status">${esc(subtitle)}</span></span><span class="kb-progress-toggle"><span class="kb-show">${en ? 'Show activity' : '展开过程'}</span><span class="kb-hide">${en ? 'Hide activity' : '收起过程'}</span><span class="kb-progress-count">${steps.length}</span><span class="kb-progress-chevron" aria-hidden="true">⌄</span></span></summary><div class="kb-progress-body"><ol class="kb-progress-steps">${rows(steps)}</ol>${steps.length ? '' : `<p class="tf-small">${en ? 'Waiting for the first execution event…' : '等待第一条执行记录…'}</p>`}</div></details>`;
}

export function updateAgentProgress(container, run, lang, expanded = false) {
  const template = document.createElement('template');
  template.innerHTML = renderAgentProgress(run, lang, expanded);
  const next = template.content.firstElementChild;
  const current = container.querySelector('.kb-progress');
  if (!current) { container.replaceChildren(next); return; }
  // Preserve the activity indicator and disclosure state across polling updates.
  for (const selector of ['.kb-current-agent', '.kb-current-action', '.kb-progress-count']) {
    const value = next.querySelector(selector).textContent;
    const target = current.querySelector(selector);
    if (target.textContent !== value) target.textContent = value;
  }
  current.querySelector('.kb-progress-indicator').className = next.querySelector('.kb-progress-indicator').className;
  for (const selector of ['.kb-progress-body']) {
    const value = next.querySelector(selector).innerHTML;
    const target = current.querySelector(selector);
    if (target.innerHTML !== value) target.innerHTML = value;
  }
}
