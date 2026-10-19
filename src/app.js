import { setupChat, replaceChatReply, rememberChatScroll, focusChatReply } from "./chat-ui.js";
import { attachCashChart, cashAnalysisQuestion } from "./cash-chart.js";
import { setupDocuments, parseSetupDocument, readSetupFile } from "./onboarding.js";
import { collectHumanAnswers, humanReplySummary } from './human-loop.js';
import { restoreAgentTasks, archiveConversation, retainAgentTasks, rememberAgentSession, linkedConversation, openAgentTask } from './agent-tasks.js';
import {
  translations,
  docGroups,
  docTypes,
  templateLabels,
  taskTitles,
  aiQuestions,
} from "./data.js";
import {
  money,
  date,
  isoDay,
  dayNumber,
  seriesFor,
  enrich,
  receiptCNY,
  cashEvents,
} from "./finance.js";
import { samplePartialEmail, inspectPaymentEmail, readPaymentDetails, paymentProblem, partialReceipt } from "./partial-payment.js";
import { loadWorkspace, saveWorkspace, storedFinancialState, storedBusinessRecords } from "./storage.js";
import { followupView, markNotificationsRead } from "./followups.js";
import { renderIcons } from "./icons.js";
import { createKnowledgeUI, askKnowledge, knowledgeAPI, watchAgentRun } from "./knowledge.js";

const root = document.getElementById("tradeflow-export-preview");

const $ = (s) => root.querySelector(s);

const $$ = (s) => [...root.querySelectorAll(s)];

const setupMode = new URLSearchParams(location.search).has("setup");
let setupPending = null, setupError = "", setupBusy = false;

let state = {
  lang: "zh",
  page: "home",
  context: "company",
  delayed: false,
  extended: false,
  tasks: [],
  draft: false,
  aiQuestion: "",
  aiQuestionCustom: false,
  aiDraft: "",
};

let selectedCashMovement = null;
let agentsEnabled = false;
const orderId = () => state.context === 'company' ? '' : state.context === 'fee' ? 'TF-26091' : 'TF-26104';
const knowledge = createKnowledgeUI({
  root, language: () => state.lang, order: orderId, includeFeeOrder: () => !setupMode,
  selectedDocument: () => state.ragDocumentId || '', rerender: () => render(),
  selectDocument: (doc, openChat) => {
    state.ragDocumentId = doc?.id || '';
    if (openChat) {
      state.context = doc.metadata.order_id === 'TF-26104' ? 'buyer' : doc.metadata.order_id === 'TF-26091' ? 'fee' : 'company';
      state.page = 'assistant';
      state.aiDraft = bi('读取这份付款资料，提取本次付款金额和日期；缺失的字段请向我提问。', 'Read this payment document, extract the payment amount and date, and ask me for any missing fields.');
      render(); $('#tf-ai-question')?.focus();
    }
    persist();
  },
});

function applyAgentWorkspace(snapshot) {
  if ((setupMode && !flow.setup?.complete) || !snapshot || snapshot.version < flow.version) return;
  flow.movements = snapshot.movements;
  flow.version = snapshot.version;
  flow.opening = snapshot.opening;
  flow.supplierDay = snapshot.supplierDay;
  flow.receiptDay = snapshot.receiptDay;
  flow.partialReceipt = snapshot.amountUSD < 12000 ? partialReceipt({ amountUSD: snapshot.amountUSD }) : null;
}
async function refreshAgents() {
  try {
    const status = await knowledgeAPI('/agents/status');
    agentsEnabled = status.mode === 'multi_agent';
    if (agentsEnabled) {
      const { workspace } = await knowledgeAPI('/agents/workspace');
      applyAgentWorkspace(workspace); render(); persist();
    }
  } catch { agentsEnabled = false; }
}
const monitoringTurns = new Set();
async function retrieveForTurn(turn) {
  if (monitoringTurns.has(turn.id)) return;
  monitoringTurns.add(turn.id);
  try {
    const history = flow.chat.filter(t => t !== turn && t.scope === turn.scope && t.rag?.status === 'done').slice(-4)
      .map(t => ({ question: t.question, answer: t.rag.paragraphs.map(p => p.text).join('\n').slice(0, 6000) }));
    flow.agentSessions ||= {};
    const sessionKey = JSON.stringify([turn.orderId, turn.documentId]);
    const result = turn.rag.progress?.run_id
      ? await watchAgentRun(turn.rag.progress.run_id, progress => { turn.rag.progress = progress; knowledge.updateProgress(turn); renderAgentTasks(); persist(); })
      : await askKnowledge({ question: turn.question, language: turn.language,
      document_id: turn.documentId, order_id: turn.orderId, history,
      session_id: flow.agentSessions[sessionKey] || null,
      live: agentsEnabled, onProgress: progress => {
        turn.rag.progress = progress;
        rememberAgentSession(turn, progress.session_id, flow.agentSessions);
        knowledge.updateProgress(turn); renderAgentTasks(); persist();
      },
      workspace: { version: flow.version, opening: flow.opening, supplierDay: flow.supplierDay,
        receiptDay: flow.receiptDay, amountUSD: flow.partialReceipt?.amountUSD || 12000 } });
    rememberAgentSession(turn, result.session_id, flow.agentSessions);
    if (result.mode === 'multi_agent') { agentsEnabled = true; applyAgentWorkspace(result.workspace); }
    turn.rag = { ...result, status: 'done' };
    turn.unread = state.page !== 'assistant' || docScope() !== turn.scope || turn.archived;
  } catch (error) { turn.rag = { status: 'error', error: error.message, progress: turn.rag.progress }; }
  monitoringTurns.delete(turn.id);
  if (state.page === 'assistant' && docScope() === turn.scope) {
    if (!replaceChatReply(root, turn, ragReply(turn), state.lang)) render();
    renderAgentTasks();
  } else if (state.page === 'home') render();
  else renderAgentTasks();
  persist();
}
function renderAgentTasks() {
  const host = $('#tx-agent-tasks');
  const tasks = flow.chat.filter(t => t.id && t.rag);
  const pending = tasks.filter(t => t.rag.status === 'pending');
  const unread = tasks.filter(t => t.unread);
  host.hidden = !tasks.length;
  if (!tasks.length) return;
  const visible = [...new Set([...pending, ...unread, ...tasks.slice(-8) ])].reverse();
  const label = t => t.rag.task_status === 'needs_approval' && t.rag.proposal?.status === 'confirmed' ? bi('已确认并更新', 'Confirmed and updated') : t.rag.human_response ? bi('已回答', 'Answered') : t.rag.status === 'pending' ? bi('后台运行中', 'Running in background')
    : t.rag.status === 'error' || t.rag.task_status === 'failed' ? bi('需要查看', 'Needs attention')
    : t.rag.task_status === 'needs_information' ? bi('待补充信息', 'Needs information')
    : t.rag.task_status === 'needs_approval' ? bi('待确认', 'Needs confirmation') : t.unread ? bi('新结果', 'New result') : bi('已查看', 'Viewed');
  host.innerHTML = `<button class="tx-agent-task-toggle" data-agent-tasks-toggle aria-expanded="${!!state.agentTasksOpen}">✦ ${bi('AI 任务', 'AI tasks')} · ${pending.length ? bi(`${pending.length} 项运行中`, `${pending.length} running`) : unread.length ? bi(`${unread.length} 条新结果`, `${unread.length} new results`) : bi('查看结果', 'View results')}</button>${state.agentTasksOpen ? `<section class="tx-agent-task-list"><strong>${bi('切换页面后继续运行', 'Tasks continue across pages')}</strong>${visible.map(t => `<button data-agent-task="${t.id}"><span>${escapeHtml(t.orderId || bi('企业整体', 'Company'))} · ${label(t)}</span><strong>${escapeHtml(t.question)}</strong></button>`).join('')}</section>` : ''}`;
}
root.addEventListener('click', event => {
  const toggle = event.target.closest('[data-agent-tasks-toggle]');
  if (toggle) { state.agentTasksOpen = !state.agentTasksOpen; renderAgentTasks(); }
  const button = event.target.closest('[data-agent-task]');
  if (!button) return;
  const turn = openAgentTask(flow.chat, button.dataset.agentTask);
  const sessionId = turn.rag.session_id || turn.rag.progress?.session_id;
  if (sessionId) {
    flow.agentSessions ||= {};
    flow.agentSessions[JSON.stringify([turn.orderId, turn.documentId])] = sessionId;
  }
  state.context = turn.scope; state.page = 'assistant'; state.ragDocumentId = turn.documentId || '';
  state.agentTasksOpen = false;
  render(); persist();
  focusChatReply(root, turn.id);
});

function saveHumanDraft(event) {
  const form = event.target.closest('[data-human-form]');
  if (!form) return;
  const turn = flow.chat.find(t => t.id === form.dataset.humanForm);
  const questionId = event.target.dataset.humanQuestion || event.target.dataset.humanComment;
  if (!questionId) return;
  turn.humanDraft ||= {};
  const draft = turn.humanDraft[questionId] ||= {};
  if (event.target.dataset.humanQuestion) draft.choice = event.target.value;
  else draft.comment = event.target.value;
  persist();
}
root.addEventListener('input', saveHumanDraft);
root.addEventListener('change', saveHumanDraft);
const humanSubmissions = new Set();
async function submitHumanReply(turn, skipAll) {
  if (humanSubmissions.has(turn.id) || turn.rag.human_response) return;
  let answers;
  try { answers = collectHumanAnswers(turn, skipAll); }
  catch { turn.humanError = bi('请为每个问题选择、留言或选「暂不回答」。', 'For each question, choose an option, leave a note, or select Skip.'); render(); return; }
  humanSubmissions.add(turn.id);
  const form = root.querySelector(`[data-human-form="${turn.id}"]`);
  for (const button of form.querySelectorAll('button')) button.disabled = true;
  turn.humanError = '';
  try {
    const response = await knowledgeAPI(`/agents/runs/${turn.rag.run_id}/answers`, {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({answers,language:state.lang})
    });
    turn.rag.human_response = response;
    const next = {id:crypto.randomUUID(),scope:turn.scope,orderId:turn.orderId,documentId:turn.documentId,archived:turn.archived,
      language:state.lang,question:humanReplySummary(response,state.lang),snapshot:financialSnapshot(),
      rag:{status:'pending',progress:response}};
    flow.chat.push(next);
    flow.agentSessions ||= {};
    rememberAgentSession(next, response.session_id, flow.agentSessions);
    persist(); render(); retrieveForTurn(next);
  } catch (error) { turn.humanError = error.message; render(); }
  humanSubmissions.delete(turn.id);
}
root.addEventListener('submit', event => {
  const form = event.target.closest('[data-human-form]');
  if (!form) return;
  event.preventDefault();
  submitHumanReply(flow.chat.find(t => t.id === form.dataset.humanForm), false);
});
root.addEventListener('click', event => {
  const button = event.target.closest('[data-human-skip]');
  if (button) submitHumanReply(flow.chat.find(t => t.id === button.dataset.humanSkip), true);
});

function startRetrieval(turn) {
  turn.id = crypto.randomUUID();
  turn.language = state.lang; turn.documentId = state.ragDocumentId || null; turn.orderId = orderId() || null;
  turn.rag = { status: 'pending' };
  retrieveForTurn(turn);
}
root.addEventListener('toggle', event => {
  if (!event.target.matches('.kb-progress')) return;
  const turnId = event.target.closest('[data-progress-turn]').dataset.progressTurn;
  const turn = flow.chat.find(item => item.id === turnId);
  if (turn.progressOpen === event.target.open) return;
  turn.progressOpen = event.target.open;
  persist();
}, true);

function ragReply(turn) {
  const finance = /资金|现金|缺口|cash|shortfall|liquidity/i.test(turn.question);
  return `<div class="tx-chat-user" data-user-content>${escapeHtml(turn.question)}</div><div class="tx-chat-reply" data-reply-id="${turn.id}" data-chat-status="${turn.rag.status}"><span class="sx-eyebrow">CashWeave</span>${knowledge.answer(turn)}${finance && turn.rag.status === "done" ? `<details class="kb-finance-note"><summary>${bi('当前演示账本', 'Current demo ledger')} · v${turn.snapshot.v}</summary><p>${bi('可用人民币：', 'Available CNY: ')}${money(turn.snapshot.opening)} · ${bi('56 天预计最大缺口：', '56-day projected peak shortfall: ')}${money(turn.snapshot.peak)}<br>${bi('由资金计算模块计算；资料检索不会改动账本。', 'Calculated by the cash engine; document retrieval does not change the ledger.')}</p></details>` : ''}</div>`;
}
root.addEventListener('click', async event => {
  const button = event.target.closest('button'); if (!button) return;
  if (button.dataset.agentConfirm) {
    button.disabled = true;
    try {
      const result = await knowledgeAPI('/agents/proposals/' + button.dataset.agentConfirm + '/confirm', { method: 'POST' });
      applyAgentWorkspace(result.workspace);
      for (const t of flow.chat) if (t.rag?.proposal?.id === result.proposal_id) t.rag.proposal.status = 'confirmed';
      state.extended = false; state.delayed = false;
      render(); persist();
      toast(bi('预计收款与资金看板已更新；实际到账余额不变。', 'Receipt forecast and dashboard updated; actual bank cash is unchanged.'));
      askAi(bi('我已确认付款字段，请重新分析资金影响并给出下一步建议。', 'I confirmed the payment fields. Analyze the updated cash impact and recommend next steps.'), state.context);
    } catch (e) { toast(e.message); button.disabled = false; }
  }
  if (button.dataset.kbCite) {
    const [turnId, sourceId] = button.dataset.kbCite.split(':');
    const source = flow.chat.find(t => t.id === turnId)?.rag?.sources.find(s => s.id === Number(sourceId));
    if (source) { try { await knowledge.open(source.document_id, source.version, source); } catch (e) { toast(e.message); } }
  }
  if (button.dataset.kbRetry) {
    const turn = flow.chat.find(t => t.id === button.dataset.kbRetry);
    turn.rag = { status: 'pending', progress: turn.rag.progress }; render(); retrieveForTurn(turn);
  }
});

const labels = {
  assistant: ["AI 助手", "从业务问题开始，把分析连接到订单、资金和行动。"],
  overview: ["今天，先关注资金安排", "围绕出口订单，掌握收款进度与近期支出。"],
  orders: ["出口订单", "一笔订单，关联合同、发票、回款与采购付款。"],
  reconcile: ["回款对账", "把到账记录与出口发票核对，集中处理差额。"],
  cash: ["资金安排", "按实际可用币种安排付款，比较回款变化的影响。"],
  tasks: ["资料与待办", "让补证、催收与付款协商有明确的下一步。"],
};

function balances() {
  return seriesFor({
    movements: flow.movements,
    opening: flow.opening,
    partialReceipt: flow.partialReceipt ? { ...flow.partialReceipt } : null,
    supplierDay: flow.supplierDay + (state.extended ? 10 : 0),
    receiptDay: flow.receiptDay + (state.delayed ? 14 : 0),
  });
}

function summary() {
  let b = balances(),
    first = b.find((x) => x.v < 0);
  return {
    first,
    gap: first ? -first.v : 0,
    peak: Math.max(0, -Math.min(...b.map((x) => x.v))),
  };
}

const orders = `<div class="tf-order"><div><strong>TF-26091 · Nordlicht GmbH</strong><div class="tf-small">德国 · LED 台灯 · 已发运</div><div class="tf-small">发票 $20,000 · 到账 $19,970</div></div><div class="tf-orderaction"><span class="tf-badge warn">差额 $30</span><button type="button" class="tf-link" data-action="fee">交给助手分析 ↗</button></div></div><div class="tf-order"><div><strong>TF-26104 · Harbour Supplies</strong><div class="tf-small">英国 · 文具套装 · 备货中</div><div class="tf-small">待收尾款 $12,000 · 采购款 ¥160,000</div></div><div class="tf-orderaction"><span class="tf-badge warn">先付款，后回款</span><button type="button" class="tf-link" data-action="buyer">分析回款延期 ↗</button></div></div>`;

function reconcile() {
  return `<section class="tf-panel"><div class="tf-panelhead"><h3>待处理差额</h3><span class="tf-badge warn">1 笔需补证</span></div><div class="tf-details"><div class="tf-detailrow"><span>订单 / 发票</span><strong>TF-26091 / INV-091</strong></div><div class="tf-detailrow"><span>买方</span><strong>Nordlicht GmbH · 德国</strong></div><div class="tf-detailrow"><span>发票金额</span><strong>$20,000</strong></div><div class="tf-detailrow"><span>净到账金额</span><strong>$19,970</strong></div><div class="tf-detailrow"><span>待解释差额</span><strong>$30</strong></div><div class="tf-context">买方邮件称差额为银行手续费，待补充汇款凭证和费用承担条款。</div></div><button type="button" class="tf-button primary" data-action="fee" style="margin-top:16px">分析差额并准备补证</button></section><section class="tf-panel"><h3>关联资料</h3><div class="tf-order"><div>INV-091 发票<div class="tf-small">文本型 PDF · 已关联</div></div><span class="tf-badge">可查看</span></div><div class="tf-order"><div>10/16 美元收款记录<div class="tf-small">银行流水 · 第 18 行</div></div><span class="tf-badge">已导入</span></div></section>`;
}

function toast(t) {
  $("#tf-toast").textContent = t;
  $("#tf-toast").hidden = false;
  localize();
}

root.addEventListener("click", (e) => {
  let b = e.target.closest("button");
  if (!b) return;
  if (b.hasAttribute("data-case-analyze")) {
    askAi(
      aiQuestions[state.context === "fee" ? "fee" : "gap"],
      state.context === "fee" ? "fee" : "buyer",
    );
    return;
  }
  if (b.dataset.case) {
    selectCase(b.dataset.case);
    state.page = "overview";
    render();
    persist();
    return;
  }
  if (b.dataset.language) {
    state.lang = b.dataset.language;
    render();
    persist();
    return;
  }
  if (b.dataset.aiPrompt) {
    askAi(aiQuestions[b.dataset.aiPrompt], b.dataset.aiPrompt);
    return;
  }
  if (b.dataset.page) {
    state.page = b.dataset.page;
    if (state.page === "home") state.context = "company";
    if (state.page === "assistant" && !state.aiQuestion) {
      state.aiQuestion = aiQuestions[state.context === "fee" ? "fee" : "gap"];
      state.aiQuestionCustom = false;
    }
    render();
    persist();
    return;
  }
  let a = b.dataset.action;
  if (!a) return;
  if (a === "ai-submit") {
    submitAi();
    return;
  }
  if (a === "side-submit") {
    const v = $("#tf-question").value.trim();
    if (v)
      askAi(
        v,
        /30|德国|差额|fee|german|difference/i.test(v) ? "fee" : "buyer",
        true,
      );
    return;
  }
  if (a === "ai-open") {
    state.page = "assistant";
    state.aiQuestion = aiQuestions[state.context];
    state.aiQuestionCustom = false;
  }
  if (a === "ai-new") {
    for (const key of Object.keys(flow.agentSessions || {})) {
      if (JSON.parse(key)[0] === (orderId() || null)) delete flow.agentSessions[key];
    }
    archiveConversation(flow.chat, docScope());
    state.aiQuestion = "";
    state.aiDraft = "";
    state.aiQuestionCustom = false;
  }
  if (a === "orders") state.page = "orders";
  if (a === "documents") state.page = "documents";
  if (["gap", "fee", "buyer"].includes(a)) {
    selectCase(a);
    state.page = "assistant";
    state.aiQuestion = aiQuestions[a];
    toast(
      "已将" +
        (a === "fee"
          ? "德国订单差额"
          : a === "buyer"
            ? "英国订单回款"
            : "当前资金情景") +
        "传入助手。",
    );
  }
  if (a === "extension") {
    state.extended = !state.extended;
    state.page = "cash";
    state.context = "buyer";
    toast(
      bi(
        "已更新额外模拟情景，已确认的约定日期保持不变。",
        "Additional scenario updated; the confirmed agreed date is unchanged.",
      ),
    );
  }
  if (a === "draft") {
    state.draft = true;
    state.page = "tasks";
    toast("已生成示例邮件草稿，保存在资料与待办中。");
  }
  if (a.startsWith("add-")) {
    let id = a.slice(4);
    if (!state.tasks.includes(id)) {
      state.tasks.push(id);
      toast("已加入待办：" + taskTitles[id]);
    } else toast("该待办已存在，可在「资料与待办」查看。");
  }
  render();
  persist();
});

root.addEventListener("change", (e) => {
  if (e.target.id === "tf-ai-scope") {
    selectCase(e.target.value);
    render();
    persist();
    return;
  }
  if (e.target.id === "tf-scenario") {
    state.delayed = e.target.value === "delay";
    selectCase("buyer");
    render();
    toast("情景图表与助手上下文已同步更新。");
    persist();
  }
});

const localeKeys = Object.keys(translations).sort(
  (a, b) => b.length - a.length,
);

const originalText = new WeakMap(),
  originalAttrs = new WeakMap();

function translate(s) {
  if (state.lang !== "en") return s;
  if (/^\d+ 项$/.test(s))
    return s.replace(" 项", Number(s.split(" ")[0]) === 1 ? " task" : " tasks");
  if (/^[-\d.]+万$/.test(s)) return String(Number(s.slice(0, -1)) * 10) + "k";
  let match = s.match(/^(.+) 预计出现 (.+) 缺口$/);
  if (match) return `${match[1]}: projected shortfall ${match[2]}`;
  match = s.match(/^当前情景下，(.+) 将首次出现 $/);
  if (match) return `The first shortfall on ${match[1]} is `;
  for (const k of localeKeys) s = s.split(k).join(translations[k]);
  return s.replaceAll("。", ".");
}

function localize() {
  root.lang = state.lang === "en" ? "en" : "zh-CN";
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    if (
      n.parentElement?.closest(
        "script,style,[data-language-control],[data-user-content]",
      )
    )
      continue;
    if (!originalText.has(n)) originalText.set(n, n.nodeValue);
    n.nodeValue = translate(originalText.get(n));
  }
  [root, ...root.querySelectorAll("[aria-label],[placeholder]")].forEach(
    (el) => {
      if (!originalAttrs.has(el))
        originalAttrs.set(el, {
          label: el.getAttribute("aria-label"),
          placeholder: el.getAttribute("placeholder"),
        });
      const a = originalAttrs.get(el);
      if (a.label !== null) el.setAttribute("aria-label", translate(a.label));
      if (a.placeholder !== null)
        el.setAttribute("placeholder", translate(a.placeholder));
    },
  );
  $$("[data-language]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.language === state.lang)),
  );
}

function escapeHtml(value) {
  return String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
}

root.addEventListener("submit", (e) => {
  if (e.target.id === "tf-ai-form") {
    e.preventDefault();
    submitAi();
  }
});

root.addEventListener("input", (e) => {
  if (e.target.id === "tf-ai-question") state.aiDraft = e.target.value;
});

const bi = (zh, en) => (state.lang === "en" ? en : zh);

function selectCase(kind) {
  selectedCashMovement = null;
  state.ragDocumentId = "";
  state.context = kind;
  state.aiQuestion = "";
  state.aiDraft = "";
  state.aiQuestionCustom = false;
}

function caseName() {
  return state.context === "fee"
    ? "TF-26091 · Nordlicht GmbH"
    : "TF-26104 · Harbour Supplies";
}

function caseTasks() {
  return state.tasks.filter((t) =>
    state.context === "fee" ? t === "receipt" : t !== "receipt",
  );
}

labels.overview = ["让回款赶上付款", "先解决订单上的资金问题，再安排下一步。"];

labels.assistant = ["AI 助手", "围绕当前订单的证据、情景与行动展开分析。"];

labels.reconcile = ["核对订单证据", "查看当前订单的合同、流水与待确认事项。"];

labels.tasks = ["订单行动与资料", "把当前订单的分析转为可以跟进的行动。"];

let docUploads = {};

let docGroup = "receipts";

let docNotice = "";

const docScope = () =>
  state.context === "company"
    ? "company"
    : state.context === "fee"
      ? "fee"
      : "buyer";

const docKey = (d) =>
  (d.scope === "company" ? "company" : docScope()) + ":" + d.id;

function isPriority(d) {
  return (
    d.priority === docScope() ||
    (d.priority === "extended" && state.extended && docScope() === "buyer")
  );
}

function sampleExists(d) {
  return d.sample === true || d.sample === docScope();
}

function docStatus(d) {
  const job = flow.jobs.find(
    (j) => j.type === d.id && (j.scope === docScope() || d.scope === "company"),
  );
  if (job)
    return bi(
      {
        queued: "待解析",
        clarifying: "待补充金额与日期",
        parsing: "解析中",
        review: "待确认字段",
        confirmed: "已确认 · 已同步",
      }[job.status],
      {
        queued: "Queued",
        clarifying: "Clarify amount and date",
        parsing: "Parsing",
        review: "Awaiting confirmation",
        confirmed: "Confirmed · Synced",
      }[job.status],
    );
  let added = docUploads[docKey(d)] || [];
  return added.length
    ? bi("已上传至知识库", "Uploaded to library")
    : sampleExists(d)
      ? bi("已有示例", "Sample available")
      : bi("待补充", "Not added");
}

function documentsView() {
  if (activeJob()?.type === "partialPayment") return `${knowledge.view()}<details class="sx-details"><summary>${bi("查看示例付款处理记录", "View guided sample history")}</summary>${partialConversation(activeJob())}</details>`;
  return `${knowledge.view()}<details class="sx-details"><summary>${bi("浏览全部资料类型", "Browse all document types")}</summary><div class="sx-detail-content">${docGroups
    .map(
      ([id, zh, en]) =>
        `<details class="sx-doc-group"><summary>${bi(zh, en)}</summary>${docTypes
          .filter((doc) => doc.group === id)
          .map(docRow)
          .join("")}</details>`,
    )
    .join("")}</div></details>`;
}

function docRow(d) {
  const records = docUploads[docKey(d)] || [],
    priority = isPriority(d);
  return `<article class="tx-doc-row"><div class="tx-doc-description"><div class="tx-doc-title"><h3>${bi(...d.name)}</h3><span class="tf-badge ${priority ? "warn" : ""}">${priority ? bi("当前问题优先", "Priority for this issue") : d.need === "base" ? bi("基础资料", "Core record") : d.need === "optional" ? bi("选用时补充", "When needed") : bi("发生时补充", "When applicable")}</span></div><p>${bi(...d.purpose)}</p><p class="tf-small">${bi("核实字段：", "Fields to verify: ")}${bi(...d.fields)}</p><span class="tf-small">${d.scope === "company" ? bi("归属：企业共用 · 无需每笔订单重复上传", "Scope: company-wide · Reuse across orders") : bi("归属：", "Scope: ") + caseName()}</span></div><div class="tx-doc-upload"><label for="doc-${d.id}">${bi("添加", "Add")} ${bi(...d.name)}</label><input id="doc-${d.id}" type="file" multiple data-doc-upload="${d.id}" accept=".pdf,.csv,.xlsx,.txt,.eml,.docx,.md,.json,.png,.jpg,.jpeg,.webp" aria-label="${bi("上传", "Upload")} ${bi(...d.name)}"><span class="tf-note">PNG / JPG / WEBP / PDF / DOCX / TXT / EML / CSV / XLSX · ${bi("每份 ≤ 10 MB，最多 5 份", "≤ 10 MB each, up to 5 files")}</span><span class="tf-badge">${docStatus(d)}</span>${sampleExists(d) ? `<span class="tf-small">${bi("已关联预置业务示例", "Linked to the preset business example")}</span>` : ""}${records.map((f, i) => `<div class="tx-doc-file"><span data-user-content>${escapeHtml(f.name)}</span>${templateLabels[d.id] ? `<button type="button" class="tf-link" data-parse-file="${d.id}" data-file-index="${i}">${bi("演示解析", "Demo extraction")}</button>` : ""}<button type="button" class="tf-link" data-doc-remove="${d.id}" data-doc-index="${i}">${bi("移除", "Remove")}</button></div>`).join("")}</div></article>`;
}

root.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.docGroup) {
    docGroup = b.dataset.docGroup;
    docNotice = "";
    render();
    persist();
  }
  if (b.dataset.docRemove) {
    const d = docTypes.find((d) => d.id === b.dataset.docRemove);
    docUploads[docKey(d)]?.splice(Number(b.dataset.docIndex), 1);
    render();
    persist();
  }
});

root.addEventListener("change", async (e) => {
  const id = e.target.dataset.docUpload;
  if (!id) return;
  const type = docTypes.find(d => d.id === id), files = [...e.target.files];
  const key = docKey(type); docUploads[key] ||= [];
  for (const file of files) {
    try {
      const record = await knowledge.upload(file, type.scope === 'company' ? '' : orderId());
      docUploads[key].push({ name: file.name, size: file.size, documentId: record.document_id });
    } catch (error) { toast(error.message); return; }
  }
  render(); persist();
});

labels.documents = [
  "业务资料",
  "按业务环节补齐证据，为当前订单的分析提供依据。",
];

let flow = {
  version: 1,
  supplierDay: 5,
  receiptDay: 12,
  opening: setupMode ? 0 : 128000,
  setup: setupMode ? { records: {}, complete: false } : null,
  jobs: [],
  chat: [],
};

function renderSetup() {
  const records = flow.setup.records;
  const next = setupDocuments.find(item => !records[item.id]);
  const count = Object.keys(records).length;
  const fields = setupPending?.fields;
  const labels = { opening: ["人民币期初余额", "Opening CNY"], usd: ["独立美元余额", "Separate USD balance"], order: ["订单编号", "Order ID"], outstanding: ["待收金额（USD）", "Outstanding USD"], receiptDay: ["预计回款日", "Expected receipt date"], payable: ["采购应付（CNY）", "Supplier payable CNY"], supplierDay: ["采购付款日", "Supplier due date"] };
  $(".tf-heading").hidden = true;
  $("#tx-case-ribbon").hidden = true;
  $("#tx-agent-tasks").hidden = true;
  $("#tx-notification-control").innerHTML = "";
  $("#tx-notification-panel").hidden = true;
  $(".tf-nav").innerHTML = `<button aria-current="page">${bi("建立工作台", "Set up workspace")}</button><button disabled>${bi("订单与资金看板", "Orders & cash")}</button><button disabled>${bi("AI 助手", "AI assistant")}</button>`;
  $("#tf-content").innerHTML = `<section class="co-intro"><div><span class="sx-eyebrow">${bi("从零开始 · 演示企业", "START FROM ZERO · DEMO BUSINESS")}</span><h1>${bi("先有资料，再有判断。", "Start with evidence.")}</h1><p>${bi("没有预置订单、资金预测或 AI 结论。导入并确认三份资料，建立企业工作台。", "No preloaded orders, forecasts or AI answers. Import and confirm three records to build your workspace.")}</p></div></section>
    <div class="setup-status"><span>${bi("已确认资料", "Confirmed records")} <strong>${count} / 3</strong></span><span>${bi("订单", "Orders")} <strong>${records.sales ? 1 : 0}</strong></span><span>${bi("人民币余额", "CNY balance")} <strong>${records.cash ? money(records.cash.fields.opening) : "—"}</strong></span></div>
    <ol class="setup-steps">${setupDocuments.map((item,index) => `<li class="${records[item.id] ? 'done' : next?.id === item.id ? 'active' : ''}"><b>${records[item.id] ? '✓' : index+1}</b><span>${bi(...item.label)}</span></li>`).join('')}</ol>
    <section class="tf-panel ow-entry"><span class="sx-eyebrow">${next ? bi(`第 ${count+1} 步`, `STEP ${count+1}`) : bi("基础资料已齐全", "BASELINE READY")}</span><h1>${next ? bi(...next.label) : bi("现在，可以看清资金安排了。", "Your cash picture is ready.")}</h1><p>${next ? bi(...next.purpose) : bi("将已确认的账户余额、订单和付款条款关联，计算首次资金缺口。", "Connect the confirmed balances, order and supplier terms to calculate the first cash shortfall.")}</p>
    ${next ? `<button class="tf-link setup-download" data-setup-sample ${setupBusy ? "disabled" : ""}>${bi("读取本步示例文件", "Read the sample file")} ↗</button>${setupPending ? `<p class="tf-small" data-user-content>${escapeHtml(setupPending.file.name)}</p><dl class="setup-fields">${Object.entries(fields).map(([key,value]) => `<div><dt>${bi(...labels[key])}</dt><dd>${key.endsWith('Day') ? date(value) : typeof value === 'number' ? value.toLocaleString('en-US') : escapeHtml(value)}</dd></div>`).join('')}</dl><p class="tf-note">${bi("字段来自上传的文本；确认后保存原件并加入知识库。", "Fields come from the uploaded text. Confirm to save the source in the knowledge library.")}</p><div class="ow-entry-action"><button class="tf-button primary" data-setup-confirm ${setupBusy ? 'disabled' : ''}>${setupBusy ? bi("正在保存…", "Saving…") : bi("确认并导入", "Confirm & import")}</button><button class="tf-link" data-setup-reselect ${setupBusy ? 'disabled' : ''}>${bi("重新选文件", "Choose another file")}</button></div>` : `<label class="ow-file-label setup-file" for="setup-file">↑ ${bi("选择资料，读取字段", "Choose a file to read its fields")}</label><input id="setup-file" class="ow-file-input" type="file" accept=".txt,.docx" aria-label="${bi("上传基础资料", "Upload baseline record")}"><p class="tf-note">${bi("可上传示例 Word 或 TXT，或直接读取示例文件；本步由程序读取字段。", "Upload the sample Word or TXT file, or read it directly above. Fields are read without an AI call.")}</p>`}` : `<button class="tf-button primary setup-open" data-setup-open>${bi("生成订单与资金看板", "Build orders & cash dashboard")} →</button>`}
    <p class="setup-error" role="status">${escapeHtml(setupError)}</p></section>
    ${count ? `<details class="sx-details"><summary>${bi("查看已导入资料", "View imported records")}</summary>${setupDocuments.filter(item=>records[item.id]).map(item=>`<p class="setup-record">✓ ${bi(...item.label)} · ${escapeHtml(records[item.id].filename)}</p>`).join('')}</details>` : ''}`;
  localize();
  $(".tf-company").textContent = bi("新企业工作台", "New business workspace");
}

root.addEventListener('change', async event => {
  if (event.target.id !== 'setup-file') return;
  const file = event.target.files[0];
  if (!file) return;
  const next = setupDocuments.find(item => !flow.setup.records[item.id]);
  setupError = ''; setupPending = null; setupBusy = true; render();
  try { setupPending = { kind: next.id, file, fields: parseSetupDocument(next.id, await readSetupFile(file)) }; }
  catch (error) { setupError = error.message; }
  setupBusy = false; render();
});
root.addEventListener('click', async event => {
  if (event.target.closest('[data-setup-sample]')) {
    const next = setupDocuments.find(item => !flow.setup.records[item.id]);
    setupError = ''; setupBusy = true; render();
    try {
      const response = await fetch('/demo/baseline/' + next.file);
      if (!response.ok) throw Error('Could not load the sample file.');
      const file = new File([await response.blob()], next.file);
      setupPending = { kind: next.id, file, fields: parseSetupDocument(next.id, await readSetupFile(file)) };
    } catch (error) { setupError = error.message; }
    setupBusy = false; render();
  }
  if (event.target.closest('[data-setup-reselect]')) { setupPending = null; setupError = ''; render(); }
  if (event.target.closest('[data-setup-confirm]')) {
    setupBusy = true; setupError = ''; render();
    try {
      const pending = setupPending;
      const doc = await knowledge.upload(pending.file, pending.kind === 'cash' ? '' : 'TF-26104');
      flow.setup.records[pending.kind] = { fields: pending.fields, filename: pending.file.name, documentId: doc.document_id || doc.id };
      setupPending = null; persist();
    } catch (error) { setupError = error.message; }
    setupBusy = false; render();
  }
  if (event.target.closest('[data-setup-open]')) {
    const { cash, sales, supplier } = flow.setup.records;
    flow.opening = cash.fields.opening;
    flow.receiptDay = sales.fields.receiptDay;
    flow.supplierDay = supplier.fields.supplierDay;
    flow.feeRemaining = 0;
    flow.setup.complete = true;
    state.page = 'home'; state.context = 'company';
    $(".tf-company").textContent = bi("星帆出口贸易 · 深圳", "StarSail Exports · Shenzhen");
    persist(); render(); window.scrollTo({top:0});
  }
});

function financialSnapshot() {
  const q = summary();
  return {
    v: flow.version,
    peak: q.peak,
    gap: q.gap,
    first: q.first?.d ?? null,
    opening: flow.opening,
    partialReceipt: flow.partialReceipt ? { ...flow.partialReceipt } : null,
    supplierDay: flow.supplierDay + (state.extended ? 10 : 0),
    receiptDay: flow.receiptDay + (state.delayed ? 14 : 0),
    extended: state.extended,
    delayed: state.delayed,
    feeRemaining: flow.feeRemaining ?? 30,
  };
}

function activeJob() {
  return flow.jobs.find((j) => j.scope === docScope());
}

function newJob(type, name, local = false) {
  if (!templateLabels[type]) {
    docNotice = bi(
      "该类资料可记录文件名；完整演示支持延期确认、客户回款通知和账户余额。",
      "This category records filenames. The full demo supports supplier extensions, buyer notices and account balances.",
    );
    render();
    return;
  }
  const scope = docScope();
  if (scope === "fee" && !["balance", "receiptEvidence"].includes(type)) {
    toast(
      bi(
        "请切换到英国订单演示付款日期变化。",
        "Switch to the UK order to demonstrate payment date changes.",
      ),
    );
    return;
  }
  const old = activeJob();
  if (old && old.status !== "confirmed") {
    toast(
      bi(
        "请先完成或取消当前资料处理。",
        "Complete or cancel the current document first.",
      ),
    );
    return;
  }
  const j = {
    id: String(Date.now()),
    scope,
    type,
    name,
    local,
    status: "queued",
    date:
      type === "extension"
        ? isoDay(
            flow.plan?.status === "pending"
              ? flow.plan.target
              : Math.min(flow.supplierDay + 10, 55),
          )
        : type === "buyerpromise"
          ? "2026-11-12"
          : "2026-10-17",
    amount:
      type === "receiptEvidence"
        ? 30
        : type === "balance"
          ? 168000
          : type === "extension"
            ? 160000
            : 12000,
    feeParty: "seller",
    approved: false,
  };
  j.sourceDate = j.date;
  flow.jobs = [j, ...flow.jobs];
  if (scope === "company") state.page = "documents";
  else setOrderStep(2);
  docGroup = type === "balance" ? "receipts" : "followup";
  render();
  persist();
}

function parseJob() {
  const j = activeJob();
  if (!j || j.status !== "queued") return;
  j.status = "parsing";
  render();
  persist();
  setTimeout(() => {
    const current = flow.jobs.find((x) => x.id === j.id);
    if (!current || current.status !== "parsing") return;
    current.status = "review";
    render();
    persist();
  }, 1100);
}

function applyConfirmedFields() {
  const j = activeJob();
  if (!j || j.status !== "review") return;
  captureFields();
  let day = dayNumber(j.date);
  if (!j.approved) {
    toast(
      bi(
        "请勾选已核对来源与字段。",
        "Confirm that you checked the source and fields.",
      ),
    );
    return;
  }
  if (
    !Number.isInteger(day) ||
    day < 0 ||
    day > 55 ||
    !Number.isFinite(j.amount) ||
    j.amount <= 0 ||
    j.amount > 100000000 ||
    (j.type === "balance" && day !== 0)
  ) {
    toast(
      bi(
        "请填写有效金额与演示期内日期；期初余额截至日应为 10/17。",
        "Enter a valid amount and date within the demo horizon; opening balance date must be Oct 17.",
      ),
    );
    return;
  }
  j.before = financialSnapshot();
  if (j.type === "extension") {
    flow.supplierDay = day;
    state.extended = false;
  }
  if (j.type === "buyerpromise") {
    flow.receiptDay = day;
    flow.partialReceipt = null;
    state.delayed = false;
  }
  if (j.type === "balance") flow.opening = j.amount;
  if (j.type === "receiptEvidence") {
    j.feeBefore = flow.feeRemaining ?? 30;
    flow.feeRemaining = j.feeParty === "seller" ? 0 : 30;
    j.feeAfter = flow.feeRemaining;
  }
  flow.version++;
  j.status = "confirmed";
  j.version = flow.version;
  j.after = financialSnapshot();
  render();
  persist();
}

function captureFields() {
  const j = activeJob();
  if (!j || j.status !== "review") return;
  const dateInput = $("#tx-field-date"),
    amountInput = $("#tx-field-amount"),
    check = $("#tx-field-check");
  if (dateInput) j.date = dateInput.value;
  if (amountInput) j.amount = Number(amountInput.value);
  if (check) j.approved = check.checked;
  const party = $("#ow-fee-party");
  if (party) j.feeParty = party.value;
  const confirm = $('[data-flow-action="confirm"]');
  if (confirm && state.page === "overview") confirm.disabled = !j.approved;
}

function flowPanel() {
  if (activeJob()?.type === "partialPayment") return partialConversation(activeJob());
  const j = activeJob();
  if (j && j.status !== "confirmed")
    return `<section class="tf-panel sx-document">${jobPanel(j)}</section>`;
  if (j?.status === "confirmed")
    return `<section class="tf-panel sx-document">${jobPanel(j)}<details class="sx-more-docs"><summary>${bi("继续添加资料", "Add another document")}</summary>${documentStart()}</details></section>`;
  return `<section class="tf-panel sx-document"><span class="sx-eyebrow">${bi("先补充影响判断的资料", "Start with decision-relevant evidence")}</span><h1>${docScope() === "fee" ? bi("核实这笔回款差额。", "Explain the receipt difference.") : bi("一份确认，就能更新整个安排。", "One confirmation updates the whole plan.")}</h1><p>${docScope() === "fee" ? bi("在下方资料库添加汇款凭证、银行费用和费用承担条款。", "Use the library below for remittance advice, bank charges and fee terms.") : bi("选择资料、核对字段，订单和资金预测会一起更新。", "Choose a document and verify its fields to update the order and cash forecast.")}</p>${docScope() === "fee" ? "" : documentStart()}</section>`;
}

function renderJobDetails(j) {
  const n = ["queued", "parsing", "review", "confirmed"].indexOf(j.status);
  const src =
    j.type === "extension"
      ? bi(
          `供应商确认：TF-26104 的人民币 160,000 元采购款，付款日调整至 ${j.sourceDate || j.date}，无额外费用。`,
          `Supplier confirms: the CNY 160,000 payment for TF-26104 moves to ${j.sourceDate || j.date} with no extra fee.`,
        )
      : j.type === "buyerpromise"
        ? bi(
            "买方通知：TF-26104 尾款 USD 12,000 预计延期。演示假设 11 月 12 日结汇可用，净额仍为人民币 80,000 元。",
            "Buyer notice: the USD 12,000 balance for TF-26104 is delayed. The demo assumes CNY 80,000 net proceeds become available on Nov 12.",
          )
        : bi(
            "账户余额示例：截至 2026 年 10 月 17 日，可用人民币余额为 168,000 元。",
            "Sample account balance: available CNY balance is 168,000 as of Oct 17, 2026.",
          );
  return `<div class="tx-flow-steps">${[bi("已选择资料", "File selected"), bi("模拟解析", "Demo extraction"), bi("确认字段", "Verify fields"), bi("更新业务", "Update records")].map((s, i) => `<span class="${i <= n ? "active" : ""}">${i + 1} · ${s}</span>`).join(" → ")}</div><p class="tf-small" data-user-content>${escapeHtml(j.name)}</p>${j.local ? `<p class="tf-note">${bi("以下字段来自演示模板，并非对所选文件内容的提取。", "Fields below come from the demo template, not from the selected file contents.")}</p>` : ""}
 ${j.status === "queued" ? `<button type="button" class="tf-button primary" data-flow-action="parse">${bi("开始模拟解析", "Start demo extraction")}</button><button type="button" class="tf-link" data-flow-action="cancel">${bi("取消", "Cancel")}</button>` : j.status === "parsing" ? `<p role="status">${bi("正在识别资料类型、定位字段与来源…", "Identifying document type, fields and source locations…")}</p>` : j.status === "review" ? `<div class="tx-extraction"><div><span class="tf-small">${bi("示例来源片段 · 第 1 段", "Sample source · Paragraph 1")}</span><blockquote>${src}</blockquote></div><div class="tx-fields"><label>${bi("关联范围", "Linked scope")}<input value="${j.type === "balance" ? bi("企业共用 · CNY 账户", "Company-wide · CNY account") : "TF-26104"}" readonly></label><label>${j.type === "extension" ? bi("新付款日期", "New payment date") : j.type === "buyerpromise" ? bi("预计结汇可用日（假设）", "Expected CNY availability (assumption)") : bi("余额截至日", "Balance as-of date")}<input id="tx-field-date" type="date" min="2026-10-17" max="2026-12-11" value="${escapeHtml(j.date)}"></label><label>${j.type === "buyerpromise" ? bi("客户尾款（USD）", "Buyer balance (USD)") : bi("金额（CNY）", "Amount (CNY)")}<input id="tx-field-amount" type="number" min="0.01" max="100000000" step="0.01" value="${j.amount}" ${j.type === "balance" ? "" : "readonly"}></label><label class="tx-confirm"><input id="tx-field-check" type="checkbox" ${j.approved ? "checked" : ""}>${bi("已核对来源、字段及关联订单", "I checked the source, fields and linked order")}</label><div class="tf-small">${bi("确认前不改动订单和现金预测；可在此修正日期。", "Orders and cash forecasts stay unchanged until confirmation; correct the date here if needed.")}</div><button type="button" class="tf-button primary" data-flow-action="confirm">${bi("确认字段并更新业务", "Confirm fields and update records")}</button><button type="button" class="tf-link" data-flow-action="cancel">${bi("取消本次处理", "Cancel this import")}</button></div></div>` : `<div class="tx-update-summary" role="status"><strong>${bi("已确认 · 订单与资金看板已更新", "Confirmed · Order and cash dashboard updated")} · v${j.version}</strong><p>${j.type === "balance" ? bi("期初余额：", "Opening balance: ") + money(j.before.opening) + " → " + money(j.after.opening) : j.type === "extension" ? bi("采购付款日期：", "Supplier payment date: ") + date(j.before.supplierDay) + " → " + date(j.after.supplierDay) : bi("预计回款日期：", "Expected receipt date: ") + date(j.before.receiptDay) + " → " + date(j.after.receiptDay)}</p><p>${bi("最高资金缺口：", "Peak cash shortfall: ")}${money(j.before.peak)} → ${money(j.after.peak)}</p><p class="tf-small">${j.type === "buyerpromise" ? bi("更新的是预期回款情景，订单仍为未收款。", "The expected receipt scenario changed; the order remains unpaid.") : j.type === "extension" ? bi("采购应付总额不变，更新约定付款日期。", "The payable amount is unchanged; the agreed payment date changed.") : bi("更新期初可用余额，不新增一笔收款。", "The opening balance changed; no extra receipt was added.")}</p><div class="tx-flow-start"><button type="button" class="tf-button primary" data-flow-action="reanalyze">${bi("让 AI 按新资料重新分析", "Ask AI to reanalyze the new evidence")}</button><button type="button" class="tf-button" data-page="cash">${bi("查看资金变化", "View cash changes")}</button><button type="button" class="tf-link" data-page="overview">${bi("查看订单状态", "View order status")}</button></div></div>`}`;
}

function chatAnswer(t) {
  if (t.followupType === "receipt") return bi(`已到预计回款核实日 ${date(t.snapshot.receiptDay)}。请补充覆盖该日期的银行流水或结汇凭证，核实实际到账金额与可用日期，再更新订单和现金流。目前没有新到账证据，不能仅凭缺少记录判断客户未付款。`, `The expected receipt check is due on ${date(t.snapshot.receiptDay)}. Add a bank statement or FX receipt covering that date, then verify the amount and availability before updating the order and cash view. A missing record alone does not establish non-payment.`);
  if (t.scope !== "fee" && t.snapshot.partialReceipt) return partialAnalysis(t.snapshot);
  if (t.scope === "fee" && t.snapshot.feeRemaining === 0)
    return bi(
      "新确认的汇款凭证与费用条款已解释 USD 30 差额，计入卖方承担的手续费；银行实际到账仍为 USD 19,970。建议保存这两份依据，并在下一笔订单中提前明确汇款费用承担方。",
      "The confirmed remittance advice and fee terms explain the USD 30 difference as seller-borne charges. Actual cash received remains USD 19,970. Retain both records and agree charge responsibility in the next order.",
    );
  if (t.scope === "fee")
    return bi(
      "该订单仍有 $30 差额需要核对汇款凭证、银行费用及承担条款。更新余额或付款日期不会自动结清该发票。",
      "The $30 difference still requires remittance advice, bank charges and fee-allocation terms. Updating a balance or payment date does not settle the invoice.",
    );
  return t.snapshot.peak
    ? bi(
        `按当前已确认资料和所选情景，采购款安排在 ${date(t.snapshot.supplierDay)}，客户尾款预计 ${date(t.snapshot.receiptDay)} 结汇可用。首次资金缺口出现在 ${date(t.snapshot.first)}，为 ${money(t.snapshot.gap)}，56 天内最高缺口为 ${money(t.snapshot.peak)}。建议先协调收付款时间，再结合物流等支出安排跟进。`,
        `Using confirmed evidence and the selected scenario, the supplier payment is on ${date(t.snapshot.supplierDay)} and buyer proceeds are expected on ${date(t.snapshot.receiptDay)}. The first shortfall is ${money(t.snapshot.gap)} on ${date(t.snapshot.first)}, with a 56-day peak of ${money(t.snapshot.peak)}. Coordinate collection and payment timing alongside logistics costs.`,
      )
    : bi(
        `当前资料下，采购款在 ${date(t.snapshot.supplierDay)} 支付，客户尾款预计 ${date(t.snapshot.receiptDay)} 可用，56 天内未出现资金缺口。继续跟进客户付款与其他已安排支出；应收款尚未转为实际到账。`,
        `With the supplier payment on ${date(t.snapshot.supplierDay)} and buyer funds expected on ${date(t.snapshot.receiptDay)}, no shortfall occurs over 56 days. Continue tracking collection and other scheduled costs; the receivable is not an actual receipt.`,
      );
}

function submitAi() {
  const q = $("#tf-ai-question")?.value.trim();
  if (q) askAi(q, state.context, true);
}

root.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.fillQuestion) {
    state.aiDraft = b.dataset.fillQuestion;
    render();
    $("#tf-ai-question")?.focus();
    persist();
  }
  if (b.dataset.demoDoc)
    newJob(b.dataset.demoDoc, "DEMO-" + b.dataset.demoDoc + ".txt");
  if (b.dataset.parseFile) {
    const d = docTypes.find((d) => d.id === b.dataset.parseFile),
      f = docUploads[docKey(d)]?.[Number(b.dataset.fileIndex)];
    if (f) {
      newJob(d.id, f.name, true);
      parseJob();
    }
  }
  const a = b.dataset.flowAction;
  if (a === "parse") parseJob();
  if (a === "confirm") commitJob();
  if (a === "cancel") {
    if (state.page === "overview") setOrderStep(1);
    flow.jobs = flow.jobs.filter((j) => j !== activeJob());
    render();
    persist();
  }
  if (a === "reanalyze")
    askAi(
      bi(
        "帮我根据刚确认的资料重新分析订单与资金影响",
        "Reanalyze the order and cash impact using the evidence just confirmed",
      ),
      state.context,
    );
});

root.addEventListener("input", (e) => {
  if (e.target.id.startsWith("tx-field-")) {
    captureFields();
    persist();
  }
});

function cashSchedule() {
  const s = financialSnapshot();
  const rows = [
    [s.supplierDay, bi("供应商货款", "Supplier payment"), -160000],
    [s.receiptDay, bi("预计尾款结汇", "Expected buyer proceeds"), receiptCNY(s)],
    [20, bi("物流等支出", "Logistics and costs"), -42000],
    [30, bi("其他回款", "Other receipts"), 120000],
    [40, bi("其他支出", "Other payments"), -38000],
    [50, bi("其他回款", "Other receipts"), 65000],
  ].sort((a, b) => a[0] - b[0]);
  return (
    '<div class="tf-tablewrap"><table><thead><tr><th>' +
    bi("日期", "Date") +
    "</th><th>" +
    bi("事项", "Item") +
    "</th><th>CNY</th></tr></thead><tbody>" +
    rows
      .map(
        ([d, label, value]) =>
          "<tr><td>" +
          date(d) +
          "</td><td>" +
          label +
          "</td><td>" +
          signedMoney(value) +
          "</td></tr>",
      )
      .join("") +
    "</tbody></table></div>"
  );
}

const signedMoney = (n) => (n < 0 ? "−" : "") + money(n);

function currentBase() {
  return {
    movements: flow.movements,
    v: flow.version,
    opening: flow.opening,
    partialReceipt: flow.partialReceipt ? { ...flow.partialReceipt } : null,
    supplierDay: flow.supplierDay,
    receiptDay: flow.receiptDay,
    extended: false,
    delayed: false,
  };
}

function latestChange() {
  return flow.jobs.find(
    (j) => j.status === "confirmed" && j.after?.v === flow.version,
  );
}

function comparison() {
  if (state.page === "home") {
    const base = enrich(currentBase());
    return {
      current: base,
      base,
      label: bi("当前安排", "Current schedule"),
      sim: false,
    };
  }
  if (state.page === "overview" && activeJob()?.status === "confirmed") {
    const job = activeJob();
    return { current: job.after, base: job.before, label: bi("资料更新前", "Before evidence update"), sim: false };
  }
  const current = financialSnapshot(),
    j = latestChange(),
    sim = state.delayed || state.extended;
  return {
    current:
      state.page === "overview" && j?.status === "confirmed"
        ? j.after
        : current,
    base: sim ? enrich(currentBase()) : j?.before || enrich(currentBase()),
    label: sim
      ? bi("已确认安排", "Confirmed schedule")
      : j
        ? bi("资料更新前", "Before evidence update")
        : bi("当前安排", "Current schedule"),
    sim,
  };
}

function button(page, zh, en, primary = false) {
  return `<button type="button" class="tf-button ${primary ? "primary" : ""}" data-page="${page}">${bi(zh, en)}</button>`;
}

function askButton(zh, en, question) {
  return `<button type="button" class="tf-link" data-connected-question="${escapeHtml(question || bi(zh, en))}">${bi(zh, en)} ↗</button>`;
}

function caseRibbon() {
  return `<div class="co-breadcrumb ow-breadcrumb"><button class="tf-link" data-page="home">← ${bi("企业总览", "Company overview")}</button><span>/</span><select id="cx-order" aria-label="${bi("选择当前订单", "Select current order")}"><option value="buyer" ${docScope() === "buyer" ? "selected" : ""}>TF-26104 · Harbour Supplies</option>${setupMode ? "" : `<option value="fee" ${docScope() === "fee" ? "selected" : ""}>TF-26091 · Nordlicht GmbH</option>`}</select></div>`;
}

function changeNotice() {
  const j = latestChange();
  if (!j) return "";
  return `<div class="cx-change"><span>${bi("最新资料已同步", "Latest evidence synced")} · v${j.version}</span><strong>${bi(...templateLabels[j.type])}</strong><span>${bi("资金缺口", "Cash shortfall")} ${money(j.before.peak)} → ${money(j.after.peak)}</span><button type="button" class="tf-link" data-flow-action="reanalyze">${bi("重新分析", "Reanalyze")} ↗</button></div>`;
}

function orderStep() {
  const job = activeJob();
  return (
    state.orderSteps?.[docScope()] ||
    (job?.status === "confirmed" ? 3 : job ? 2 : 1)
  );
}

function setOrderStep(step) {
  state.orderSteps ||= {};
  state.orderSteps[docScope()] = step;
  state.page = "overview";
}

function orderProgress(step) {
  const job = activeJob();
  const available = job?.status === "confirmed" ? 4 : job ? 2 : 1;
  return `<nav class="ow-progress" aria-label="${bi("订单处理步骤", "Order workflow")}">${[
    ["补充资料", "Evidence"],
    ["确认字段", "Verify"],
    ["资金影响", "Cash impact"],
    ["AI 分析", "AI analysis"],
  ]
    .map(
      ([zh, en], index) =>
        `<button type="button" data-order-step="${index + 1}" ${index + 1 > available ? "disabled" : ""} ${step === index + 1 ? 'aria-current="step"' : ""}><span>${index + 1 < step ? "✓" : index + 1}</span>${bi(zh, en)}</button>`,
    )
    .join("")}</nav>`;
}

function orderUpload() {
  const fee = docScope() === "fee";
  const type =
    state.orderDocType?.[docScope()] ||
    (fee
      ? "receiptEvidence"
      : flow.plan?.status === "pending"
        ? "extension"
        : "partialPayment");
  const descriptions = {
    partialPayment: ["客户只说先付一部分。让助手读邮件、找出缺项，再补充金额与日期。", "The buyer promises only a partial payment. Let the assistant read the email and clarify the missing amount and date."],
    buyerpromise: [
      "核对尾款金额与预计到账时间，判断是否影响供应商付款。",
      "Check the balance and expected receipt date against supplier payments.",
    ],
    extension: [
      "核对供应商同意的付款日期，更新这笔订单的采购付款安排。",
      "Verify the agreed payment date and update the supplier schedule.",
    ],
    receiptEvidence: [
      "核对 USD 30 差额的来源，以及手续费由哪一方承担。",
      "Identify the USD 30 difference and who bears the transfer charge.",
    ],
  };
  return `<section class="tf-panel ow-entry"><span class="sx-eyebrow">${bi("当前任务 · 补充付款依据", "NEXT STEP · ADD PAYMENT EVIDENCE")}</span><h1>${fee ? bi("这笔回款，为什么少了 USD 30？", "Why is this receipt USD 30 short?") : bi("补充客户的付款安排", "Add the buyer’s payment plan")}</h1><p>${fee ? bi("补充汇款凭证与费用条款，让 AI 帮你核对差额。", "Add the remittance record and fee terms to investigate the difference.") : bi("上传邮件，核对金额和日期，再更新资金预测。", "Upload the email, verify the amount and date, then update the forecast.")}</p><div class="ow-order-facts"><div><span>${bi("待收尾款", "Outstanding")}</span><strong>${fee ? "USD 30" : "USD 12,000"}</strong></div><div><span>${bi("采购款到期", "Supplier due")}</span><strong>${fee ? "—" : date(flow.supplierDay) + " · ¥160,000"}</strong></div></div><div class="ow-entry-action">${button("documents", "上传或选择订单资料", "Add order evidence", true)}</div></section><details class="sx-details ow-sample"><summary>${bi("使用示例体验完整流程", "Try the guided sample workflow")}</summary><div class="ow-sample-body"><div class="ow-upload"><label for="ow-document-type">${bi("这次补充什么资料？", "What are you adding?")}</label><select id="ow-document-type">${(fee ? ["receiptEvidence"] : ["partialPayment", "buyerpromise", "extension"]).map((id) => `<option value="${id}" ${id === type ? "selected" : ""}>${bi(...templateLabels[id])}</option>`).join("")}</select><p>${bi(...descriptions[type])}</p><label class="ow-file-label" for="ow-file">↑ ${bi("选择资料文件", "Choose a document")}</label><input id="ow-file" class="ow-file-input" type="file" accept="${type === "partialPayment" ? ".txt,.eml" : ".pdf,.txt,.csv,.xlsx,.eml,.png,.jpg,.jpeg"}" aria-label="${bi("上传订单资料", "Upload order evidence")}"><span class="tf-note">${type === "partialPayment" ? bi("TXT / 纯文本 EML · 同步上传知识库", "TXT / plain-text EML · Uploaded to the knowledge library") : "PDF / TXT / CSV / XLSX / EML"}</span></div><div class="ow-footer"><p class="tf-note">${type === "partialPayment" ? bi("本地规则演示 · 示例邮件不含付款金额和日期", "Local demo · The sample omits the payment amount and date") : bi("交互演示 · 上传后使用示例字段模拟解析", "Interactive demo · Uploads use sample extraction fields")}</p><button class="tf-button primary" data-order-action="sample">${bi("使用示例继续", "Continue with sample")} →</button></div></div></details>`;
}

function startOrderEvidence(type, name, local = false) {
  if (type === "partialPayment") { startPartialPayment(name, samplePartialEmail); return; }
  const pending = activeJob();
  if (pending && pending.status !== "confirmed")
    flow.jobs = flow.jobs.filter((job) => job.id !== pending.id);
  newJob(type, name, local);
  parseJob();
}

function orderSource(job) {
  if (job.type === "receiptEvidence")
    return bi(
      "汇款凭证：付款 USD 20,000，银行手续费 USD 30，净入账 USD 19,970。合同条款：收款行手续费由卖方承担。",
      "Remittance advice: USD 20,000 paid, USD 30 bank charge, USD 19,970 net credited. Contract: receiving-bank charges are borne by the seller.",
    );
  if (job.type === "extension")
    return bi(
      `供应商确认：TF-26104 采购款 CNY 160,000，付款日期调整为 ${job.sourceDate || job.date}，无额外费用。`,
      `Supplier confirms: CNY 160,000 for TF-26104 is payable on ${job.sourceDate || job.date}, with no extra fee.`,
    );
  if (job.type === "buyerpromise")
    return bi(
      "客户通知：TF-26104 尾款 USD 12,000 将延期支付。示例采用 11 月 12 日作为预计结汇可用日，净额 CNY 80,000。",
      "Buyer notice: the USD 12,000 balance for TF-26104 will be delayed. The example assumes CNY 80,000 net proceeds available on November 12.",
    );
  return bi(
    "账户余额：2026 年 10 月 17 日可用人民币余额为 168,000 元。",
    "Account balance: CNY 168,000 available on October 17, 2026.",
  );
}

function orderVerification(job) {
  if (job.type === "partialPayment") return partialConversation(job);
  if (job.status === "queued" || job.status === "parsing")
    return `<section class="tf-panel ow-current"><span class="sx-eyebrow">${bi("第 2 步 / 提取字段", "STEP 2 / EXTRACTION")}</span><h1>${bi("正在整理这份资料", "Preparing your evidence")}</h1><p class="ow-intro" data-user-content>${escapeHtml(job.name)}</p><div class="ow-processing" role="status"><span></span>${bi("模拟解析资料，定位日期、金额和关联订单…", "Extracting sample dates, amounts and order references…")}</div>${job.status === "queued" ? `<button class="tf-button primary" data-flow-action="parse">${bi("继续解析", "Resume extraction")}</button>` : ""}</section>`;
  const confirmed = job.status === "confirmed",
    fee = job.type === "receiptEvidence";
  return `<section class="tf-panel ow-current"><span class="sx-eyebrow">${bi("第 2 步 / 确认字段", "STEP 2 / VERIFY FIELDS")}</span><h1>${confirmed ? bi("已确认的字段", "Confirmed fields") : bi("核对后，再更新订单", "Verify before updating")}</h1><p class="ow-intro" data-user-content>${escapeHtml(job.name)} · ${bi("示例解析", "Sample extraction")}</p><details class="ow-source"><summary>${bi("核对来源原文", "Review source excerpt")}</summary><blockquote>${orderSource(job)}</blockquote></details><div class="ow-fields"><label>${bi("关联订单", "Linked order")}<input value="${job.scope === "fee" ? "TF-26091" : "TF-26104"}" readonly></label>${fee ? `<label>${bi("银行净到账（USD）", "Net bank receipt (USD)")}<input value="19,970" readonly></label><label>${bi("银行手续费（USD）", "Bank charge (USD)")}<input value="30" readonly></label><label>${bi("费用承担方", "Charge responsibility")}<select id="ow-fee-party" ${confirmed ? "disabled" : ""}><option value="seller" ${job.feeParty !== "buyer" ? "selected" : ""}>${bi("卖方承担", "Seller")}</option><option value="buyer" ${job.feeParty === "buyer" ? "selected" : ""}>${bi("买方承担，仍需追收", "Buyer; balance remains due")}</option></select></label>` : `<label>${job.type === "extension" ? bi("采购付款日期", "Supplier payment date") : job.type === "buyerpromise" ? bi("预计结汇可用日", "Expected CNY availability") : bi("余额截至日", "Balance as-of date")}<input id="tx-field-date" type="date" min="2026-10-17" max="2026-12-11" value="${job.date}" ${confirmed ? "readonly" : ""}></label><label>${job.type === "buyerpromise" ? bi("尾款金额（USD）", "Buyer balance (USD)") : bi("金额（CNY）", "Amount (CNY)")}<input id="tx-field-amount" type="number" value="${job.amount}" ${job.type !== "balance" || confirmed ? "readonly" : ""}></label>`}</div>${confirmed ? `<div class="ow-footer"><button class="tf-link" data-order-action="edit">${bi("修改字段", "Revise fields")}</button><button class="tf-button primary" data-order-step="3">${bi("查看资金影响", "View cash impact")} →</button></div>` : `<label class="tx-confirm ow-confirm"><input id="tx-field-check" type="checkbox" ${job.approved ? "checked" : ""}>${bi("我已核对来源、字段与关联订单", "I checked the source, fields and linked order")}</label><div class="ow-footer"><button class="tf-link" data-flow-action="cancel">${bi("重新选择资料", "Choose another document")}</button><button class="tf-button primary" data-flow-action="confirm" ${job.approved ? "" : "disabled"}>${bi("确认并查看资金影响", "Confirm & view cash impact")} →</button></div>`}</section>`;
}

function orderImpact(job) {
  const fee = job.type === "receiptEvidence",
    before = job.before,
    after = job.after;
  const changes = job.type === "partialPayment"
    ? [
        [bi("本次预计结汇净额", "Expected net proceeds"), money(receiptCNY(before)), money(receiptCNY(after))],
        [bi("预计人民币可用日", "Expected CNY availability"), date(before.receiptDay), date(after.receiptDay)],
        [bi("未排期尾款（USD）", "Unscheduled balance (USD)"), String(before.partialReceipt?.remainingUSD || 0), String(after.partialReceipt.remainingUSD)],
        [bi("56 天最大缺口", "56-day peak shortfall"), money(before.peak), money(after.peak)],
      ]
    : fee
    ? [
        [
          bi("待收差额", "Remaining receivable"),
          `USD ${job.feeBefore ?? 30}`,
          `USD ${job.feeAfter}`,
        ],
        [bi("银行到账", "Bank receipt"), "USD 19,970", "USD 19,970"],
      ]
    : [
        [
          job.type === "extension"
            ? bi("采购付款日", "Supplier due date")
            : job.type === "buyerpromise"
              ? bi("预计结汇可用日", "Expected CNY availability")
              : bi("期初人民币余额", "Opening CNY balance"),
          job.type === "balance"
            ? money(before.opening)
            : date(
                job.type === "extension"
                  ? before.supplierDay
                  : before.receiptDay,
              ),
          job.type === "balance"
            ? money(after.opening)
            : date(
                job.type === "extension" ? after.supplierDay : after.receiptDay,
              ),
        ],
        [
          bi("56 天最大资金缺口", "56-day peak shortfall"),
          money(before.peak),
          money(after.peak),
        ],
      ];
  return `<section class="tf-panel ow-current"><span class="sx-eyebrow">${bi("第 3 步 / 资金影响", "STEP 3 / CASH IMPACT")}</span><h1>${bi("这份资料，改变了什么？", "What changed with this evidence?")}</h1><p class="ow-intro">${bi("字段已确认，订单与企业资金看板已同步。", "Fields confirmed. The order and company dashboard are updated.")}</p><div class="ow-footer ow-impact-action"><button class="tf-link" data-order-step="2">← ${bi("核对字段", "Review fields")}</button><button class="tf-button primary" data-order-action="analyze">${bi("让 AI 分析下一步", "Ask AI for next steps")} →</button></div><div class="ow-change-table"><div class="ow-change-head"><span>${bi("变化项", "Item")}</span><span>${bi("确认前", "Before")}</span><span>${bi("确认后", "After")}</span></div>${changes.map(([label, a, b], index) => `<div><span>${label}</span><span>${a}</span><strong class="${!fee && index === changes.length - 1 && after.peak > 0 ? "ow-warning" : ""}">${b}</strong></div>`).join("")}</div>${fee ? `<p class="ow-impact-note">${job.feeAfter === 0 ? bi("USD 30 已归入卖方承担的手续费，应收差额已解释；不会新增一笔现金收入。", "USD 30 is allocated to seller-borne bank charges. The receivable difference is resolved, with no additional cash receipt.") : bi("费用由买方承担，USD 30 仍待追收；银行实际到账保持不变。", "The buyer bears the charge; USD 30 remains due. The actual bank receipt is unchanged.")}</p>` : `<details class="ow-chart-details" data-cash-chart><summary>${bi("查看资金曲线与计算口径", "Cash chart and assumptions")}</summary><svg id="tf-chart" class="tf-chart" role="img" aria-label="${bi("资料确认前后资金预测对比", "Cash forecast before and after confirmation")}"></svg><div class="cx-legend"><span class="cx-baseline">${bi("确认前", "Before")}</span><span class="cx-current">${bi("确认后", "After")}</span></div><p class="ow-impact-note">${job.type === "partialPayment" ? bi(`仅将 USD ${after.partialReceipt.amountUSD.toLocaleString("en-US")} 纳入预计回款，剩余 USD ${after.partialReceipt.remainingUSD.toLocaleString("en-US")} 未排期。结汇净额沿用原订单比例假设；应收总额和银行余额未改变。`, `Only USD ${after.partialReceipt.amountUSD.toLocaleString("en-US")} enters the receipt forecast. USD ${after.partialReceipt.remainingUSD.toLocaleString("en-US")} remains unscheduled. Net CNY uses the existing order assumption; total receivables and bank cash are unchanged.`) : job.type === "buyerpromise" ? bi("更新的是预计回款时间，客户尾款仍未实际到账。", "The expected receipt date changed; the buyer balance is still unpaid.") : bi("根据更新后的字段重新计算，资金曲线包含企业其他订单收支。", "Recalculated with the new fields, including cash movements from other orders.")}</p></details>`}</section>`;
}

root.addEventListener("toggle", event => {
  if (event.target.matches("[data-cash-chart]") && event.target.open) chart();
}, true);

function overview() {
  const step = orderStep(),
    job = activeJob();
  return `${orderProgress(step)}${step === 1 ? orderUpload() : step === 2 ? orderVerification(job) : step === 3 ? orderImpact(job) : aiPage()}`;
}

function chartPanel() {
  const c = comparison(),
    controls = state.page === "cash";
  return `<section class="tf-panel sx-chart"><div class="tf-panelhead"><h3>${bi("未来的资金够不够？", "Will the cash be enough?")}</h3><span class="tf-small">${bi("56 天 · 人民币", "56 days · CNY")}</span></div>${controls ? `<div class="sx-controls"><label>${bi("客户回款", "Buyer receipt")}<select id="tf-scenario"><option value="base" ${!state.delayed ? "selected" : ""}>${bi("按预计日期", "Expected date")}</option><option value="delay" ${state.delayed ? "selected" : ""}>${bi("晚付 14 天", "14 days late")}</option></select></label><label>${bi("供应商付款", "Supplier payment")}<select id="sx-extension"><option value="base" ${!state.extended ? "selected" : ""}>${bi("按约定日期", "Agreed date")}</option><option value="extend" ${state.extended ? "selected" : ""}>${bi("协商延期 10 天", "Negotiate 10 more days")}</option></select></label></div>` : ""}<svg id="tf-chart" class="tf-chart" role="img" aria-label="${bi("56 天人民币余额", "56-day CNY cash balance")}"></svg><div class="cx-legend"><span class="cx-current">${c.sim ? bi("试算方案", "Proposed scenario") : bi("当前预测", "Current forecast")}</span><span class="cx-baseline">${c.label}</span></div>${controls ? `<div class="sx-comparison"><span>${bi("最高资金缺口", "Peak shortfall")}</span><strong>${money(c.base.peak)} <span>→</span> ${money(c.current.peak)}</strong></div>` : ""}<p class="tf-note sx-chart-note">${c.sim ? bi("当前显示试算结果，确认的付款日期尚未改变。", "Showing a scenario; agreed payment dates have not changed.") : bi("按已确认资料及预计回款计算，尾款仍需跟进。", "Based on confirmed records and expected receipts; collection remains open.")}</p></section>`;
}

function chart() {
  const svg = $("#tf-chart");
  if (!svg) return;
  if (svg.parentElement.classList.contains("cash-chart-interactive")) svg.parentElement.replaceWith(svg);
  const w = Math.max(210, svg.getBoundingClientRect().width),
    h = svg.getBoundingClientRect().height,
    L = 49,
    R = 12,
    T = 19,
    B = 30,
    c = comparison(),
    a = seriesFor(c.current),
    b = seriesFor(c.base),
    values = [...a, ...b].map((x) => x.v),
    lo = Math.min(-40000, ...values),
    hi = Math.max(160000, ...values),
    x = (d) => L + (d / 55) * (w - L - R),
    y = (v) => T + ((hi - v) / (hi - lo)) * (h - T - B),
    path = (arr) =>
      arr
        .map((p, i) => (i ? `H${x(p.d)}V${y(p.v)}` : `M${x(p.d)},${y(p.v)}`))
        .join(" ");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.innerHTML = `<title>${bi("人民币余额：当前预测与对比情景", "CNY balances: current and comparison forecasts")}</title>${[lo, 0, hi].map((v) => `<line x1="${L}" y1="${y(v)}" x2="${w - R}" y2="${y(v)}" stroke="var(--tf-line)"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${Math.round(v / 1000)}k</text>`).join("")}${[0, 18, 36, 55].map((d) => `<text x="${x(d)}" y="${h - 6}" text-anchor="${d === 0 ? "start" : d === 55 ? "end" : "middle"}">${date(d)}</text>`).join("")}<path d="${path(b)}" fill="none" stroke="var(--tf-sub)" stroke-width="1.5" stroke-dasharray="5 4"/><path d="${path(a)}" fill="none" stroke="var(--tf-accent)" stroke-width="2.5"/>${c.current.first !== null ? `<circle cx="${x(c.current.first)}" cy="${y(-c.current.gap)}" r="4" fill="var(--tf-warn)"/>` : ""}`;
  attachCashChart(svg, { snapshot: c.current, points: a, baseline: b, comparisonLabel: c.label, language: state.lang, x, y, width: w, height: h, onSelect: openCashMovement });
}


function openCashMovement(event, snapshot) {
  selectCase(event.orderId ? "buyer" : "company");
  selectedCashMovement = { event, snapshot };
  state.delayed = false;
  state.extended = false;
  state.page = event.orderId ? "orders" : "assistant";
  if (!event.orderId) state.aiDraft = cashAnalysisQuestion(event, snapshot, state.lang);
  render();
  persist();
  window.scrollTo({ top: 0 });
}

function cashMovementContext() {
  if (!selectedCashMovement || state.context !== "buyer") return "";
  const { event } = selectedCashMovement;
  return `<aside class="cash-movement-context"><div><small>${bi("从资金曲线查看", "Selected from cash outlook")} · ${event.orderId}</small><p>${isoDay(event.day)} · ${bi(...event.label)} · ${event.amount < 0 ? "−" : "+"}${money(event.amount)}</p></div><button class="tf-button primary" data-analyze-cash>${bi("AI 分析资金影响", "Analyze cash impact")} →</button></aside>`;
}

root.addEventListener("click", event => {
  if (!event.target.closest("[data-analyze-cash]")) return;
  const { event: movement, snapshot } = selectedCashMovement;
  askAi(cashAnalysisQuestion(movement, snapshot, state.lang), "buyer");
});

function orderView() {
  const fee = docScope() === "fee", s = financialSnapshot();
  const resolved = fee && flow.feeRemaining === 0;
  const title = fee
    ? resolved ? bi("回款差额已核实", "Receipt difference resolved") : bi("核实 USD 30 的回款差额", "Resolve the USD 30 receipt difference")
    : s.peak ? bi("协调付款与回款日期", "Align payment and collection dates") : bi("跟进客户回款", "Follow up the buyer’s payment");
  const rows = fee ? [
    [bi("发票金额", "Invoice amount"), "USD 20,000"],
    [bi("银行实际到账", "Bank receipt"), "USD 19,970"],
    [bi("待解释差额", "Unresolved balance"), `USD ${flow.feeRemaining}`],
  ] : [
    [bi("待收尾款", "Outstanding balance"), "USD 12,000"],
    [bi("采购款到期", "Supplier payment"), `${date(flow.supplierDay)} · ¥160,000`],
    [bi("预计结汇", "Expected net proceeds"), `${date(flow.receiptDay)} · ${money(receiptCNY(flow))}`],
  ];
  return `${cashMovementContext()}<section class="tf-panel ow-current"><span class="sx-eyebrow">${bi("当前待办", "NEXT ACTION")}</span><h1>${title}</h1><p class="ow-intro">${fee ? resolved ? bi("费用已归入卖方承担的手续费，银行到账金额不变。", "The difference is recorded as seller-borne fees; bank cash is unchanged.") : bi("补充汇款凭证和费用承担条款，确认差额来源。", "Add remittance evidence and fee terms to explain the difference.") : bi(`当前企业资金预测的最大缺口为 ${money(s.peak)}，预计回款尚未到账。`, `The company forecast shows a peak shortfall of ${money(s.peak)}; expected receipts remain unpaid.`)}</p><dl class="ow-fact-list">${rows.map(([label,value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join("")}</dl><div class="ow-entry-action">${fee ? button(resolved ? "reconcile" : "documents", resolved ? "查看确认字段" : "补充凭证", resolved ? "View confirmed fields" : "Add evidence", true) : button(s.peak ? "cash" : "assistant", s.peak ? "比较付款方案" : "分析回款安排", s.peak ? "Compare payment options" : "Analyze collection", true)}</div></section><details class="sx-details"><summary>${bi("订单资料与历史变更", "Order evidence and updates")}</summary>${changeNotice()}${evidenceRows()}<div class="ow-secondary">${button("reconcile", "核对来源与字段", "Review fields")}${askButton("分析这笔订单", "Analyze this order")}</div></details>`;
}

function evidenceRows() {
  const fee = docScope() === "fee";
  const rows = fee
    ? [
        [bi("商业发票", "Commercial invoice"), "USD 20,000", "invoice"],
        [
          bi("银行流水 · 第18行", "Bank statement · Row 18"),
          "USD 19,970",
          "statement",
        ],
        [
          bi("费用承担条款", "Fee allocation terms"),
          bi("待补充", "Missing"),
          "feeTerms",
        ],
      ]
    : [
        [
          bi("供应商采购合同", "Supplier purchase contract"),
          `${date(flow.supplierDay)} · CNY 160,000`,
          "purchase",
        ],
        [
          bi("客户付款条件 / 结汇假设", "Buyer terms / FX assumption"),
          receiptDescription(),
          "sales",
        ],
        [
          bi("账户可用余额", "Available account balance"),
          `10/17 · ${money(flow.opening)}`,
          "balance",
        ],
      ];
  return rows
    .map(
      ([label, value, id]) =>
        `<div class="cx-evidence-row"><div><strong>${label}</strong><p class="tf-small">${value}</p></div><button type="button" class="tf-link" data-source="${id}">${bi("查看依据", "View evidence")} ↗</button></div>`,
    )
    .join("");
}

function evidenceView() {
  const j = activeJob();
  return `<section class="tf-panel"><div class="tf-panelhead"><h3>${bi("订单使用的确认字段", "Confirmed fields used by this order")}</h3><span class="tf-badge">v${flow.version}</span></div>${evidenceRows()}<div class="tx-flow-start">${button("documents", "补充 / 修正资料", "Add / correct evidence")}${button("orders", "继续订单分析 →", "Continue to order analysis →", true)}</div></section>${j && j.status !== "confirmed" ? flowPanel() : ""}`;
}

function cashView() {
  const s = financialSnapshot();
  return `<div class="sx-journey"><span>01 ${bi("看清问题", "Understand")}</span><span class="active">02 ${bi("比较方案", "Compare")}</span><span>03 ${bi("跟进行动", "Follow up")}</span></div><div class="sx-intro"><h1>${bi("换个付款时间，会怎样？", "What if we change the payment date?")}</h1><p>${bi("调整下方两个条件，资金曲线会直接更新。", "Change either assumption to see the cash impact.")}</p></div>${chartPanel()}<section class="sx-next sx-plan"><div><h3>${s.peak ? bi("这个方案仍有缺口", "This scenario still has a gap") : bi("这个方案可以覆盖付款", "This scenario covers the payment")}</h3><p>${bi("保存为协商目标，拿到供应商确认后再更新订单。", "Save the proposal, then update the order when the supplier agrees.")}</p></div><button class="tf-button primary" data-connected="plan" ${!state.extended ? "disabled" : ""}>${bi("保存方案，去跟进", "Save plan & follow up")} →</button></section><details class="sx-details"><summary>${bi("查看逐笔收支", "View cash movements")}</summary><div class="sx-detail-content">${cashSchedule()}</div></details>`;
}

function taskView() {
  const target = flow.plan?.target,
    done = flow.plan?.status === "confirmed";
  if (!flow.plan)
    return `<section class="sx-focus"><h1>${bi("先确定一个付款方案。", "Choose a payment plan first.")}</h1>${button("cash", "比较方案", "Compare options", true)}</section>`;
  return `<div class="sx-journey"><span>01 ${bi("看清问题", "Understand")}</span><span>02 ${bi("比较方案", "Compare")}</span><span class="active">03 ${bi("跟进行动", "Follow up")}</span></div><section class="sx-focus"><span class="sx-eyebrow">${done ? bi("已确认", "Confirmed") : bi("等待供应商回复", "Awaiting supplier reply")}</span><h1>${done ? bi("付款日期已更新。", "Payment date updated.") : bi(`和供应商确认 ${date(target)} 付款。`, `Agree payment on ${date(target)}.`)}</h1><p class="sx-explanation">${bi("采购款 ¥160,000 · TF-26104 · 财务负责跟进", "CNY 160,000 · TF-26104 · Finance to follow up")}</p><div class="tf-draft">${bi(`希望将这笔订单的采购付款调整至 ${date(target)}，请确认是否同意，以及有无额外费用。`, `Could we move the supplier payment to ${date(target)}? Please confirm your agreement and any additional charges.`)}</div><p class="tf-note">${bi("协商草稿，尚未发送", "Draft for negotiation · Not sent")}</p><div class="sx-next"><p>${done ? bi("订单与资金预测已同步。", "The order and forecast are up to date.") : bi("收到确认后，核对新日期并更新资金安排。", "Once agreed, verify the new date and update the cash plan.")}</p>${done ? button("overview", "返回资金工作台", "Back to workspace", true) : `<button class="tf-button primary" data-connected="agreement">${bi("已收到确认，更新资料", "Agreement received · Update")} →</button>`}</div></section>`;
}

function conversationTurns(turns, renderTurn) {
  return turns.map(renderTurn).join("");
}

function aiPage() {
  if (!agentsEnabled && !state.ragDocumentId && activeJob()?.type === "partialPayment" && activeJob().status !== "confirmed") return partialConversation(activeJob());
  const scoped = flow.chat.filter(t => !t.archived && t.scope === docScope());
  const turns = state.page === "overview"
    ? linkedConversation(scoped, scoped.filter(t => t.snapshot.v === flow.version))
    : scoped;
  return `<section class="tx-chat"><div class="tx-chat-top"><span>${bi("AI 助手", "AI assistant")}</span><button class="tf-link" data-action="ai-new">${bi("新对话", "New chat")}</button></div><div class="tx-messages" aria-live="polite">${
    turns.length
      ? conversationTurns(turns, (t, i) => {
            const stale = t.snapshot.v !== flow.version,
              last = i === turns.length - 1;
            if (t.rag) return ragReply(t);
            return `<div class="tx-chat-user" data-user-content>${escapeHtml(t.question)}</div><div class="tx-chat-reply"><span class="sx-eyebrow">CashWeave${stale ? " · " + bi("较早资料", "Earlier evidence") : ""}</span><p>${t.kind === "missing" ? bi("请补充客户的付款通知或供应商延期确认，在资料库核对日期后，资金预测会一起更新。", "Add the buyer’s payment notice or supplier agreement. Verify its dates in Documents to update the forecast.") : chatAnswer(t)}</p>${last && state.page !== "overview" ? `<div class="tx-chat-actions">${stale ? `<button class="tf-link" data-flow-action="reanalyze">${bi("资料有更新，重新分析", "Evidence changed · Reanalyze")} →</button>` : t.scope === "fee" || t.kind === "missing" || t.followupType === "receipt" ? button("documents", "去补充资料", "Add evidence") : t.kind === "delay" ? `<button class="tf-link" data-connected="delay">${bi("把这个假设放到资金看板", "View this scenario on the dashboard")} →</button>` : `<button class="tf-link" data-simple="compare">${bi("去比较付款方案", "Compare payment options")} →</button>`}</div>` : ""}<details class="sx-sources"><summary>${bi("分析依据", "Sources")}</summary><p class="tf-small">${caseName()} · ${bi("已确认资料", "Confirmed evidence")} v${t.snapshot.v}</p>${state.page === "overview" ? `<button class="tf-link" data-order-step="2">${bi("查看确认字段", "View confirmed fields")}</button>` : button("reconcile", "查看字段", "View fields")}</details>${last && state.page === "overview" && !stale && t.followupType === "receipt" ? `<button class="tf-link ow-ai-next" data-order-step="1">${bi("补充到账凭证", "Add bank evidence")} →</button>` : last && state.page === "overview" && !stale && t.scope === "buyer" && t.snapshot.peak > 0 ? `<button class="tf-link ow-ai-next" data-simple="compare">${bi("比较付款方案", "Compare payment options")} →</button>` : ""}</div>`;
          })
      : `<div class="tx-chat-empty"><span class="sx-ai-mark">✦</span><h1>${bi("这笔订单，下一步怎么做？", "What comes next for this order?")}</h1><p>${bi("直接问，订单、资料和资金安排已经关联。", "Just ask. Your order, evidence and cash plan are connected.")}</p></div>`
  }</div><div class="tx-composer">${knowledge.composer()}<div class="tx-chat-hints" ${turns.length ? "hidden" : ""}>${[bi("帮我分析当前付款风险", "Explain the current payment risk"), docScope() === "fee" ? (flow.feeRemaining === 0 ? bi("这次确认对资金有什么影响？", "How does this confirmation affect cash?") : bi("还缺哪些回款资料？", "What receipt evidence is missing?")) : bi("客户晚付 14 天会怎样？", "What if the buyer pays 14 days late?")].map((q) => `<button data-fill-question="${escapeHtml(q)}">${q}</button>`).join("")}</div><form id="tf-ai-form"><textarea id="tf-ai-question" rows="3" maxlength="300" aria-label="${bi("向 AI 助手提问", "Ask CashWeave")}" placeholder="${bi("输入你的问题…", "Ask a question…")}">${escapeHtml(state.aiDraft || "")}</textarea><div class="tx-send-row"><span class="tf-note">${bi("Enter 换行", "Enter for a new line")}</span><button class="tf-button primary" type="button" data-action="ai-submit">${bi("发送", "Send")} ↑</button></div></form></div></section>`;
}

function askAi(question, kind) {
  if (!agentsEnabled && !state.ragDocumentId && activeJob()?.type === "partialPayment" && activeJob().status !== "confirmed") {
    clarifyPartialPayment(question);
    return;
  }
  if (flow.chat.some(t => !t.archived && t.scope === (kind === 'company' ? 'company' : docScope()) && t.rag?.status === 'pending')) return;
  if (kind === "company") {
    flow.chat.push({
      scope: "company",
      question,
      snapshot: {
        ...enrich(currentBase()),
        feeRemaining: flow.feeRemaining ?? 30,
      },
    });
    startRetrieval(flow.chat.at(-1));
    state.page = "assistant";
    state.aiDraft = "";
    render();
    persist();
    return;
  }
  const inOrderFlow = state.page === "overview" && orderStep() === 4;
  const delay = /14/.test(question) && /晚|延|delay|late/i.test(question);
  state.context = kind === "fee" ? "fee" : "buyer";
  const s = financialSnapshot();
  const snap = delay
    ? enrich({
        ...currentBase(),
        supplierDay: s.supplierDay,
        receiptDay: flow.receiptDay + 14,
        delayed: true,
      })
    : s;
  flow.chat.push({
    scope: docScope(),
    question,
    kind: delay
      ? "delay"
      : /补充|missing/i.test(question)
        ? "missing"
        : "analysis",
    snapshot: snap,
  });
  startRetrieval(flow.chat.at(-1));
  flow.chat = retainAgentTasks(flow.chat);
  state.page = inOrderFlow ? "overview" : "assistant";
  state.aiDraft = "";
  render();
  persist();
}

function jobPanel(j) {
  if (j.status === "confirmed")
    return `<div class="sx-confirmed"><span class="sx-check">✓</span><h1>${bi("已更新，回到资金安排。", "Updated. See your cash position.")}</h1><p>${bi(...templateLabels[j.type])} · ${bi("订单与 AI 已同步", "Order and AI context synced")}</p><div class="sx-comparison"><span>${bi("资金缺口", "Cash shortfall")}</span><strong>${money(j.before.peak)} → ${money(j.after.peak)}</strong></div>${button("overview", "查看更新后的安排", "See updated workspace", true)}</div>`;
  return renderJobDetails(j);
}

function commitJob() {
  const before = enrich(currentBase()),
    version = flow.version;
  applyConfirmedFields();
  const j = activeJob();
  if (j?.status === "confirmed" && flow.version > version) {
    j.before = before;
    j.after = enrich(currentBase());
    if (docScope() !== "company") setOrderStep(3);
    if (j.type === "extension" && flow.plan)
      flow.plan.status =
        flow.plan.target === flow.supplierDay ? "confirmed" : "revised";
    render();
    persist();
  }
}

function render() {
  showStorageStatus();
  if (setupMode && !flow.setup.complete) { renderSetup(); return; }
  renderAgentTasks();
  const company = state.context === "company";
  const views = {
    home: companyHome,
    overview,
    documents: company ? companyDocuments : documentsView,
    orders: orderView,
    reconcile: evidenceView,
    cash: cashView,
    tasks: taskView,
    assistant: company ? companyAi : aiPage,
  };
  rememberChatScroll(root);
  root.dataset.page = state.page;
  $("#tf-content").innerHTML = views[state.page]();
  $(".tf-heading").hidden = ["home", "overview", "assistant"].includes(state.page);
  $("#tx-case-ribbon").hidden = company;
  $("#tx-case-ribbon").innerHTML = company ? "" : caseRibbon();
  const names = {
    home: ["企业资金总览", "Company cash overview"],
    overview: ["订单处理", "Order workspace"],
    documents: ["业务资料", "Documents"],
    orders: ["订单详情", "Order details"],
    reconcile: ["资料依据", "Evidence"],
    cash: ["比较方案", "Compare options"],
    tasks: ["行动跟进", "Follow-up"],
    assistant: ["AI 助手", "AI assistant"],
  };
  $("#tf-page-title").textContent = bi(...names[state.page]);
  $("#tf-page-sub").textContent =
    state.page === "home"
      ? bi("公司全貌与订单优先级。", "Company cash and order priorities.")
      : state.page === "documents"
        ? bi(
            "选择资料 → 核对字段 → 自动更新",
            "Choose evidence → Verify fields → Update together",
          )
        : bi(
            "让订单回款，赶上经营付款。",
            "Keep receipts in time with payments.",
          );
  $(".tf-nav").innerHTML = [
    ["home", "layout-dashboard", "企业总览", "Overview"],
    ["documents", "files", "资料库", "Documents"],
    ["assistant", "sparkles", "AI 助手", "AI assistant"],
  ]
    .map(
      ([page, icon, zh, en]) =>
        `<button data-page="${page}" ${state.page === page || (page === "home" && ["overview", "cash", "tasks", "orders", "reconcile"].includes(state.page)) ? 'aria-current="page"' : ""}><i data-lucide="${icon}" aria-hidden="true"></i>${bi(zh, en)}</button>`,
    )
    .join("");
  $("#tf-toast").hidden = true;
  renderNotifications();
  localize();
  const companyRecord = storedBusinessRecords()?.company;
  if (companyRecord) $(".tf-company").textContent = companyRecord.name;
  renderIcons(root);
  setupChat(root, state.lang, `${state.page}:${docScope()}`);
  requestAnimationFrame(chart);
}

root.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.connectedQuestion) {
    askAi(b.dataset.connectedQuestion, docScope());
    return;
  }
  if (b.dataset.source) {
    const d = docTypes.find((x) => x.id === b.dataset.source);
    state.page = "documents";
    docGroup = d.group;
    render();
    $("#tf-content").insertAdjacentHTML(
      "afterbegin",
      `<section class="tf-panel cx-source"><div class="tf-panelhead"><h3>${bi("字段来源", "Field provenance")} · ${bi(...d.name)}</h3><span class="tf-badge">v${flow.version}</span></div><p>${bi(...d.purpose)}</p><p class="tf-small">${bi("核对内容：", "Check: ")}${bi(...d.fields)}</p><p class="tf-small">${bi("当前采用的字段可在「字段确认」中核对，新增资料需确认后才同步。", "Inspect current values in Verify fields; new evidence is synced after confirmation.")}</p></section>`,
    );
    persist();
    return;
  }
  const a = b.dataset.connected;
  if (!a) return;
  if (a === "scenario") {
    state.context = "buyer";
    state.extended = !state.extended;
    state.page = "cash";
  }
  if (a === "delay") {
    state.context = "buyer";
    state.delayed = true;
    state.page = "cash";
  }
  if (a === "plan") {
    if (docScope() === "fee") return;
    const target = flow.supplierDay + (state.extended ? 10 : 0);
    if (target > 55) {
      toast(
        bi(
          "协商目标超出演示期，请先调整日期。",
          "The target is outside this demo horizon.",
        ),
      );
      return;
    }
    flow.plan = { target, version: flow.version, status: "pending" };
    if (!state.tasks.includes("extension")) state.tasks.push("extension");
    state.page = "tasks";
  }
  if (a === "agreement") {
    state.context = "buyer";
    const j = flow.jobs.find(
      (x) => x.type === "extension" && x.status === "confirmed",
    );
    if (j && flow.plan?.status === "confirmed") {
      state.page = "documents";
      docGroup = "followup";
    } else {
      newJob("extension", "DEMO-supplier-agreement.txt");
      parseJob();
      return;
    }
  }
  render();
  persist();
});

root.addEventListener("change", (e) => {
  if (e.target.id === "cx-order") {
    selectCase(e.target.value);
    if (["cash", "tasks"].includes(state.page)) state.page = "overview";
    render();
    persist();
  }
});

root.addEventListener(
  "submit",
  (e) => {
    if (e.target.id === "tf-question-form" || e.target.id === "tf-ai-form") {
      e.preventDefault();
      e.stopImmediatePropagation();
      const q = e.target.querySelector("input,textarea")?.value.trim();
      if (q) askAi(q, docScope());
    }
  },
  true,
);

root.addEventListener("input", (e) => {
  if (e.target.id === "tf-ai-question") {
    state.aiDraft = e.target.value;
    persist();
  }
});

root.addEventListener("click", (event) => {
  const control = event.target.closest("button");
  if (!control) return;
  if (control.dataset.orderStep) {
    setOrderStep(Number(control.dataset.orderStep));
    render();
    persist();
    window.scrollTo({ top: 0 });
  }
  const action = control.dataset.orderAction;
  if (action === "sample") {
    const type = $("#ow-document-type").value;
    startOrderEvidence(type, "Sample-" + type + ".txt");
  }
  if (action === "edit") {
    const previous = activeJob();
    flow.jobs.unshift({
      ...previous,
      id: String(Date.now()),
      status: "review",
      approved: false,
    });
    setOrderStep(2);
    render();
    persist();
  }
  if (action === "analyze") {
    setOrderStep(4);
    askAi(
      bi(
        "根据刚确认的资料，分析这笔订单的资金影响与下一步。",
        "Explain this order’s cash impact and next steps using the confirmed evidence.",
      ),
      docScope(),
    );
    window.scrollTo({ top: 0 });
  }
});

root.addEventListener("change", async (event) => {
  if (event.target.id === "ow-document-type") {
    state.orderDocType ||= {};
    state.orderDocType[docScope()] = event.target.value;
    render();
    persist();
  }
  if (event.target.id === "ow-fee-party") {
    captureFields();
    persist();
  }
  if (event.target.id === "ow-file") {
    const file = event.target.files[0];
    if (!file) return;
    const type = $("#ow-document-type").value;
    try { await knowledge.upload(file, orderId()); }
    catch (error) { toast(error.message); return; }
    const key = docScope() + ":" + type;
    docUploads[key] ||= [];
    docUploads[key].push({ name: file.name, size: file.size });
    if (type === "partialPayment") {
      if (!/\.(txt|eml)$/i.test(file.name) || file.size > 1024 * 1024) {
        toast(bi("请上传 1 MB 以内的 TXT 或纯文本 EML 邮件。", "Upload a TXT or plain-text EML email under 1 MB."));
        return;
      }
      const content = await file.text();
      if (/Content-Type:\s*(?:text\/html|multipart\/)|Content-Transfer-Encoding:\s*(?:base64|quoted-printable)/i.test(content)) {
        toast(bi("请将邮件正文另存为 TXT 后上传。", "Save the email body as a TXT file and upload it."));
        return;
      }
      state.context = "buyer";
      startPartialPayment(file.name, content);
    } else startOrderEvidence(type, file.name, true);
  }
});

function activeBuyerPartial() {
  const job = flow.jobs.find((j) => j.scope === "buyer");
  return job?.type === "partialPayment" && job.status !== "confirmed";
}

function receiptDescription() {
  return flow.partialReceipt
    ? bi(`本次 USD ${flow.partialReceipt.amountUSD.toLocaleString("en-US")} · ${date(flow.receiptDay)} · 预计 ${money(receiptCNY(flow))}；余款 USD ${flow.partialReceipt.remainingUSD.toLocaleString("en-US")} 未排期`, `USD ${flow.partialReceipt.amountUSD.toLocaleString("en-US")} on ${date(flow.receiptDay)}, expected ${money(receiptCNY(flow))}; USD ${flow.partialReceipt.remainingUSD.toLocaleString("en-US")} unscheduled`)
    : `${date(flow.receiptDay)} · USD 12,000 → CNY 80,000`;
}

function startPartialPayment(name, content) {
  const identified = inspectPaymentEmail(content);
  if ((identified.order && identified.order !== "TF-26104") || !identified.partial) {
    toast(bi("请提供 TF-26104 的部分付款邮件，或使用示例邮件体验。", "Use a partial-payment email for TF-26104, or try the sample email."));
    return;
  }
  const pending = activeJob();
  if (pending && pending.status !== "confirmed") flow.jobs = flow.jobs.filter((j) => j.id !== pending.id);
  const draft = { amountUSD: identified.amountUSD, date: identified.date };
  flow.jobs.unshift({
    id: String(Date.now()), scope: "buyer", type: "partialPayment", name,
    content, draft, disputed: identified.disputed, extracted: { ...draft }, messages: [],
    status: paymentProblem(draft) ? "clarifying" : "review",
  });
  state.aiDraft = "";
  setOrderStep(2);
  render();
  persist();
}

function paymentPrompt(draft) {
  const issue = paymentProblem(draft);
  const messages = {
    amountMissing: draft.date
      ? bi(`已记录预计人民币可用日 ${draft.date}。客户本次具体支付多少美元？`, `Expected CNY availability is ${draft.date}. How many USD will the buyer pay in this installment?`)
      : bi("邮件只说先支付无争议部分，没有说明具体金额和日期。客户本次支付多少美元？预计哪天结汇后可用于人民币付款？", "The email promises the undisputed portion but gives no amount or date. How many USD will the buyer pay, and when will the converted CNY be available?"),
    amountRange: bi("本次部分付款金额应大于 0 且小于订单待收尾款 USD 12,000，请确认金额。", "Enter a partial payment above USD 0 and below the USD 12,000 outstanding balance."),
    dateMissing: bi(`已记录本次付款 USD ${Number(draft.amountUSD).toLocaleString("en-US")}。还需要预计人民币可用日，请按 YYYY-MM-DD 补充。`, `I have USD ${Number(draft.amountUSD).toLocaleString("en-US")} for this installment. When will the CNY be available? Use YYYY-MM-DD.`),
    dateRange: bi("请填写 2026-10-17 至 2026-12-11 之间的有效可用日期。", "Enter a valid availability date between 2026-10-17 and 2026-12-11."),
  };
  return issue ? messages[issue] : bi("金额和日期已补齐。请核对下面的付款计划，确认后我会更新订单并计算资金影响。", "The amount and date are complete. Review the payment plan below, then confirm it to update the order and calculate the cash impact.");
}

function clarifyPartialPayment(question) {
  const job = activeJob();
  const fields = readPaymentDetails(question, { reply: true });
  if (fields.amountUSD !== null) job.draft.amountUSD = fields.amountUSD;
  if (fields.date) job.draft.date = fields.date;
  job.messages.push({ question, draft: { ...job.draft } });
  job.status = paymentProblem(job.draft) ? "clarifying" : "review";
  state.aiDraft = "";
  render();
  persist();
}

function partialConversation(job) {
  const ready = job.status === "review" || job.status === "confirmed";
  const confirmed = job.status === "confirmed";
  const draft = job.draft;
  const estimate = ready ? partialReceipt(draft) : null;
  const hint = draft.amountUSD === null
    ? bi("本次先付 USD 6,000", "The buyer will pay USD 6,000 first")
    : bi("预计 2026-10-29 结汇后可用", "CNY will be available on 2026-10-29");
  const history = `<div class="tx-chat-reply"><span class="sx-eyebrow">CashWeave</span><p>${bi("这封邮件提出部分付款。已关联 Harbour Supplies 的 TF-26104，订单记录中的待收尾款是 USD 12,000。", "This email proposes a partial payment. It is linked to Harbour Supplies order TF-26104, which has USD 12,000 outstanding.")}${job.disputed ? bi(" 邮件同时提到争议处理，余款条件需要继续跟进。", " The email also mentions a dispute, so the release conditions for the remainder need follow-up.") : ""}</p><p>${paymentPrompt(job.extracted)}</p></div>
      ${job.messages.map((m) => `<div class="tx-chat-user" data-user-content>${escapeHtml(m.question)}</div><div class="tx-chat-reply"><span class="sx-eyebrow">CashWeave</span><p>${paymentPrompt(m.draft)}</p></div>`).join("")}`;
  return `<section class="tx-chat pp-chat">
    <div class="tx-chat-top"><span>${bi("第 2 步 / AI 补全付款信息", "STEP 2 / CLARIFY PAYMENT")}</span><span>TF-26104</span></div>
    <details class="pp-source"><summary>${bi("客户邮件", "Buyer email")} · <span data-user-content>${escapeHtml(job.name)}</span></summary><pre data-user-content>${escapeHtml(job.content)}</pre></details>
    <div class="tx-messages" aria-live="polite">
      ${job.messages.length || ready ? `<details class="tx-history"><summary>${bi("之前的补充记录", "Earlier clarifications")}</summary><div class="tx-history-turns">${history}</div></details>` : ""}
      ${ready ? "" : `<div class="tx-chat-reply"><span class="sx-eyebrow">CashWeave</span><p>${paymentPrompt(draft)}</p></div>`}
      ${ready ? `<div class="pp-review"><h2>${confirmed ? bi("已确认的部分付款计划", "Confirmed partial-payment plan") : bi("确认这次付款计划", "Confirm this payment plan")}</h2><p class="tf-small">${bi("字段来自邮件及你的补充，确认前不改变资金预测。", "Fields come from the email and your clarification. The forecast changes only after confirmation.")}</p><div class="ow-fields"><label>${bi("本次付款（USD）", "This installment (USD)")}<input id="pp-amount" type="number" min="0.01" max="11999.99" step="0.01" value="${draft.amountUSD}" ${confirmed ? "readonly" : ""}></label><label>${bi("预计人民币可用日", "Expected CNY availability")}<input id="pp-date" type="date" min="2026-10-17" max="2026-12-11" value="${escapeHtml(draft.date)}" ${confirmed ? "readonly" : ""}></label></div><p class="pp-estimate" id="pp-estimate">${partialEstimate(estimate)}</p><p class="tf-note">${bi("沿用原订单 USD 12,000 对应净额 CNY 80,000 的比例假设。余款不设定到账日；总应收仍为 USD 12,000，实际银行余额不变。", "Net CNY follows the existing USD 12,000 / CNY 80,000 order assumption. The remainder has no receipt date. Total receivables stay at USD 12,000 and bank cash is unchanged.")}</p><p id="pp-error" class="pp-error" role="alert"></p><div class="ow-footer">${confirmed ? `<button class="tf-link" data-order-action="edit">${bi("修改计划", "Revise plan")}</button><button class="tf-button primary" data-order-step="3">${bi("查看资金影响", "View cash impact")} →</button>` : `<button class="tf-button primary" data-partial-action="confirm">${bi("确认并更新订单与现金流", "Confirm & update order and cash")} →</button>`}</div></div>` : ""}
    </div>
    ${ready ? "" : `<div class="tx-composer"><div class="tx-chat-hints"><button data-fill-question="${escapeHtml(hint)}">${bi("试填：", "Try: ")}${hint}</button></div><form id="tf-ai-form"><textarea id="tf-ai-question" rows="2" maxlength="300" aria-label="${bi("补充付款信息", "Clarify payment details")}" placeholder="${bi("回复金额或日期，例如：先付 USD 6,000…", "Reply with the amount or date, e.g. pay USD 6,000…")}">${escapeHtml(state.aiDraft || "")}</textarea><div class="tx-send-row"><span class="tf-note">${bi("本地规则演示 · 未连接模型", "Local rule-based demo · No live model")}</span><button type="button" class="tf-button primary" data-action="ai-submit">${bi("发送", "Send")} ↑</button></div></form></div>`}
  </section>`;
}

function partialEstimate(value) {
  return bi(`预计结汇净额 ${money(value.netCNY)}，剩余 USD ${value.remainingUSD.toLocaleString("en-US")} 待确认日期。`, `Expected net proceeds ${money(value.netCNY)}. USD ${value.remainingUSD.toLocaleString("en-US")} remains unscheduled.`);
}

function confirmPartialPayment() {
  const job = activeJob();
  if (job.status === "confirmed") return;
  job.draft = { amountUSD: $("#pp-amount").value, date: $("#pp-date").value };
  if (paymentProblem(job.draft)) {
    $("#pp-error").textContent = paymentPrompt(job.draft);
    return;
  }
  job.before = enrich(currentBase());
  flow.partialReceipt = { ...partialReceipt(job.draft), evidenceId: job.id };
  flow.receiptDay = dayNumber(job.draft.date);
  flow.version++;
  state.delayed = false;
  state.extended = false;
  job.status = "confirmed";
  job.version = flow.version;
  job.after = enrich(currentBase());
  setOrderStep(3);
  render();
  persist();
}

function partialAnalysis(snapshot) {
  const p = snapshot.partialReceipt;
  const changed = bi(`本次预计 USD ${p.amountUSD.toLocaleString("en-US")}，按订单结汇假设为 ${money(p.netCNY)}，在 ${date(snapshot.receiptDay)} 可用；余款 USD ${p.remainingUSD.toLocaleString("en-US")} 仍未排期。`, `This installment is USD ${p.amountUSD.toLocaleString("en-US")}, modeled as ${money(p.netCNY)} available on ${date(snapshot.receiptDay)}. USD ${p.remainingUSD.toLocaleString("en-US")} remains unscheduled.`);
  const impact = snapshot.peak
    ? bi(` 首次缺口在 ${date(snapshot.first)}，金额 ${money(snapshot.gap)}；56 天最大缺口 ${money(snapshot.peak)}。先与供应商协商分期或延期，并预留 ${money(snapshot.peak)} 的覆盖方案。`, ` The first gap is ${money(snapshot.gap)} on ${date(snapshot.first)}, and the 56-day peak is ${money(snapshot.peak)}. Discuss split or deferred supplier payment and arrange coverage for the ${money(snapshot.peak)} peak gap.`)
    : bi(" 已排期收支下暂未出现缺口，继续跟进本次付款兑现。", " Scheduled cash flows show no shortfall. Track whether this installment arrives as expected.");
  const scenario = snapshot.extended || snapshot.delayed
    ? bi(`以下为试算：${snapshot.extended ? "供应商额外延期 10 天；" : ""}${snapshot.delayed ? "客户额外晚付 14 天；" : ""}已确认安排不变。`, `Scenario: ${snapshot.extended ? "supplier payment deferred by 10 days; " : ""}${snapshot.delayed ? "buyer payment delayed by 14 days; " : ""}the confirmed schedule is unchanged. `)
    : "";
  return scenario + changed + impact + bi(` 同时确认余款 USD ${p.remainingUSD.toLocaleString("en-US")} 的付款条件与日期。下面可比较付款方案，取得供应商同意后再更新安排。`, ` Also confirm the release conditions and timing for the remaining USD ${p.remainingUSD.toLocaleString("en-US")}. Compare payment options below, then update the schedule once the supplier agrees.`);
}

root.addEventListener("click", (event) => {
  if (event.target.closest('[data-partial-action="confirm"]')) confirmPartialPayment();
});
root.addEventListener("input", (event) => {
  if (!["pp-amount", "pp-date"].includes(event.target.id)) return;
  const job = activeJob();
  job.draft = { amountUSD: $("#pp-amount").value, date: $("#pp-date").value };
  $("#pp-error").textContent = "";
  $("#pp-estimate").textContent = paymentProblem(job.draft) ? paymentPrompt(job.draft) : partialEstimate(partialReceipt(job.draft));
  persist();
});

function persist() {
  saveWorkspace({ state, docGroup, docUploads, flow });
}

let storageStatus = {status:'loading'};
const storageLabel = document.createElement('span');
storageLabel.className = 'tx-storage-status';
$('.tf-top').append(storageLabel);
function showStorageStatus() {
  const labels = {loading:['连接数据库…','Connecting…'], saving:['正在保存…','Saving…'], saved:['已保存到数据库','Saved to database'], offline:['离线 · 仅本机缓存','Offline · Local cache'], error:['保存失败 · 请刷新','Save failed · Reload']};
  storageLabel.textContent = bi(...labels[storageStatus.status]);
  storageLabel.title = storageStatus.detail || '';
  storageLabel.setAttribute('role','status');
}
window.addEventListener('workspace-storage', event => {storageStatus=event.detail; showStorageStatus();});
window.addEventListener('workspace-financial', event => {
  if (event.detail && event.detail.version > flow.version) {applyAgentWorkspace(event.detail); render();}
});
showStorageStatus();
const saved = await loadWorkspace();
if (saved) {
  state = saved.state;
  docGroup = saved.docGroup;
  docUploads = saved.docUploads;
  flow = saved.flow;
  for (const job of flow.jobs) {
    if (job.status === "parsing") job.status = "queued";
  }
}
applyAgentWorkspace(storedFinancialState());
state.page = "home";
state.context = "company";
state.notificationsOpen = false;
state.agentTasksOpen = false;
const reconnectingTurns = restoreAgentTasks(flow.chat);
render();
persist();
knowledge.refresh();
refreshAgents();
for (const turn of reconnectingTurns) retrieveForTurn(turn);
setInterval(() => knowledge.refresh(), 4000);
new ResizeObserver(chart).observe($("#tf-content"));

function documentStart() {
  return `<div class="sx-upload-start"><label for="sx-document-type">${bi("资料类型", "Document type")}</label><select id="sx-document-type">${["extension", "buyerpromise", "balance"].map((type) => `<option value="${type}">${bi(...templateLabels[type])}</option>`).join("")}</select><button class="tf-button primary" data-simple="sample">${bi("用示例体验", "Try a sample")} →</button></div><p class="tf-note">${bi("演示使用模板解析；实际资料从下方资料库添加。", "Sample extraction uses templates. Add your files in the library below.")}</p>`;
}

root.addEventListener("click", (e) => {
  const b = e.target.closest("[data-simple]");
  if (!b) return;
  if (b.dataset.simple === "compare") {
    state.page = "cash";
    state.extended = true;
    render();
    persist();
  }
  if (b.dataset.simple === "sample") {
    newJob($("#sx-document-type").value, "Sample-document.txt");
    parseJob();
  }
});
root.addEventListener("change", (e) => {
  if (e.target.id === "sx-extension") {
    state.extended = e.target.value === "extend";
    render();
    persist();
  }
});

function companyPosition() {
  const base = currentBase(),
    summary = enrich(base),
    series = seriesFor(base);
  const payments = cashEvents(base).filter(event => event.amount < 0);
  return {
    ...summary,
    minimum: Math.min(...series.map((p) => p.v)),
    dueWeek: payments
      .filter((p) => p.day < 7)
      .reduce((sum, p) => sum - p.amount, 0),
  };
}

function companyOrders(destination = "overview") {
  const p = companyPosition();
  const buyerJob = flow.jobs.find((j) => j.scope === "buyer");
  const buyerPending = buyerJob && buyerJob.status !== "confirmed";
  const buyerStatus = buyerPending
    ? (activeBuyerPartial() ? (buyerJob.status === "review" ? bi("付款计划待确认", "Confirm payment plan") : bi("付款信息待补充", "Clarify payment")) : bi("资料待确认", "Verify evidence"))
    : flow.plan?.status === "pending"
      ? bi("等待供应商确认", "Awaiting supplier")
      : p.peak
        ? bi("付款需要协调", "Coordinate payment")
        : bi("尾款待跟进", "Follow up receipt");
  const rows = [
    {
      scope: "buyer",
      initials: "HS",
      tone: p.peak || buyerPending ? "attention" : "collection",
      next: buyerPending
        ? (activeBuyerPartial() ? (buyerJob.status === "review" ? bi("确认部分付款计划", "Confirm partial-payment plan") : bi("补充部分付款金额与日期", "Clarify amount and date")) : bi("核对新资料", "Verify new evidence"))
        : flow.plan?.status === "pending"
          ? bi("补充供应商确认", "Add supplier confirmation")
          : p.peak
            ? bi("协调收付款时间", "Review payment timing")
            : bi("跟进客户尾款", "Follow up collection"),
      name: "Harbour Supplies",
      id: "TF-26104",
      country: bi("英国 · 文具套装", "UK · Stationery"),
      status: buyerStatus,
      detail: bi(
        flow.partialReceipt ? `计划先付 USD ${flow.partialReceipt.amountUSD.toLocaleString("en-US")}，${date(flow.receiptDay)} 预计可用；余款 USD ${flow.partialReceipt.remainingUSD.toLocaleString("en-US")} 待定。` : `尾款 USD 12,000，预计 ${date(flow.receiptDay)} 可用；采购付款 ${date(flow.supplierDay)} 到期。`,
        flow.partialReceipt ? `USD ${flow.partialReceipt.amountUSD.toLocaleString("en-US")} expected on ${date(flow.receiptDay)}; USD ${flow.partialReceipt.remainingUSD.toLocaleString("en-US")} unscheduled.` : `USD 12,000 expected on ${date(flow.receiptDay)}; supplier due ${date(flow.supplierDay)}.`,
      ),
      amount: "USD 12,000",
      label: bi("待收尾款", "Outstanding"),
    },
    ...(!setupMode ? [{
      scope: "fee",
      initials: "NG",
      tone: "attention",
      next: bi("核对汇款凭证与费用条款", "Check remittance and fee terms"),
      name: "Nordlicht GmbH",
      id: "TF-26091",
      country: bi("德国 · LED 台灯", "Germany · LED lamps"),
      status:
        flow.feeRemaining === 0
          ? bi("差额已解释", "Difference resolved")
          : bi("回款差额待核实", "Verify receipt difference"),
      detail: bi(
        "发票 USD 20,000，银行到账 USD 19,970。",
        "USD 20,000 invoiced; USD 19,970 received.",
      ),
      amount: `USD ${flow.feeRemaining ?? 30}`,
      label: bi("待核差额", "Unresolved"),
    }] : []),
  ];
  const business = storedBusinessRecords();
  for (const row of rows) {
    const record = business?.trade_orders.find(order => order.id === row.id);
    if (!record) continue;
    row.name = business.counterparties.find(party => party.id === record.customer_id).name;
    row.amount = `${record.currency} ${((record.total_minor - record.received_minor - record.adjustment_minor) / 100).toLocaleString("en-US")}`;
  }
  const visibleRows =
    destination === "overview"
      ? rows.filter((row) => row.scope !== "fee" || flow.feeRemaining !== 0)
      : rows;
  return `<div class="co-orders">${visibleRows.map((order) => `<button type="button" class="co-order" data-open-order="${order.scope}" data-order-destination="${destination}"><span class="co-avatar ${order.tone}" aria-hidden="true">${order.initials}</span><div class="co-order-main"><div class="co-order-title"><strong>${escapeHtml(order.name)}</strong><span class="co-status ${order.tone}">${order.status}</span></div><span class="co-order-meta">${order.id} · ${order.country}</span><p>${order.detail}</p><span class="co-order-next">${bi("下一步", "Next")} <span>→</span> ${order.next}</span></div><div class="co-order-amount"><span>${order.label}</span><strong>${order.amount}</strong></div><span class="co-chevron" aria-hidden="true">›</span></button>`).join("")}</div>`;
}

function companyHome() {
  const p = companyPosition();
  const upcoming = cashEvents(currentBase()).slice(0, 3);
  const business = storedBusinessRecords();
  const companyName = business?.company?.name || 'StarSail Exports';
  const usdBalance = business?.bank_accounts.filter(account => account.currency === 'USD').reduce((sum, account) => sum + account.opening_minor / 100, 0) ?? 19970;
  return `<section class="co-intro"><div><span class="sx-eyebrow">${escapeHtml(companyName)} / ${bi("资金工作台", "Cash workspace")}</span><h1>${bi("每笔订单，都有下一步。", "Every order. A clear next step.")}</h1></div><span class="co-asof">${bi("2026年10月17日 · 示例企业", "17 Oct 2026 · Sample business")}</span></section>
  <section class="co-cash-card" aria-label="${bi("企业资金概况", "Company cash position")}">
    <div class="co-balances"><article><span>${bi("可用人民币", "Available CNY")}</span><strong><small>¥</small>${flow.opening.toLocaleString("en-US")}</strong><p>${bi("用于境内经营付款", "Available for domestic payments")}</p></article><article><span>${bi("可用美元", "Available USD")}</span><strong><small>$</small>${usdBalance.toLocaleString("en-US")}</strong><p>${bi("美元账户 · 尚未结汇", "USD account · Not converted")}</p></article></div>
    <div class="co-cash-summary"><div><span>${bi("7 天内待付", "Due within 7 days")}</span><strong>${money(p.dueWeek)}</strong></div><div class="${p.peak ? "co-negative" : ""}"><span>${bi("56 天最大缺口", "56-day peak shortfall")}</span><strong>${money(p.peak)}</strong></div></div>
  </section>
  <section class="co-insight ${p.peak ? "attention" : ""}" aria-label="${bi("当前需要关注", "Needs your attention")}"><span class="co-insight-icon" aria-hidden="true">${p.peak ? "!" : "↗"}</span><div><strong>${p.peak ? bi(`${date(p.first)} 预计出现资金缺口`, `Cash shortfall expected on ${date(p.first)}`) : bi("当前收付款计划下，预计无资金缺口", "No shortfall under the current cash plan")}</strong><p>${p.peak ? bi("先协调付款时间，再跟进客户回款。", "Review payment timing and follow up collections.") : bi(`未来 56 天最低余额 ${signedMoney(p.minimum)}，仍需按期收回客户尾款。`, `Lowest 56-day balance: ${signedMoney(p.minimum)}. Buyer receipts must arrive as planned.`)}</p></div><button class="tf-link" data-connected-question="${bi("帮我分析企业资金情况和优先处理的订单", "Analyze company cash and prioritize outstanding orders")}">${bi("分析原因", "Explain this")} ↗</button></section>
  <section class="co-order-section"><div class="co-section-title"><h2>${bi("需要处理的订单", "Orders needing attention")} <span>${(setupMode || flow.feeRemaining === 0) ? 1 : 2}</span></h2><p>${bi("从这笔订单开始", "Start with an order below")}</p></div>${companyOrders()}</section>
  <section class="tf-panel co-chart"><div class="tf-panelhead"><div><h3>${bi("未来资金走势", "Cash outlook")}</h3><p class="tf-small">${bi("56 天 · 人民币余额预测", "56 days · Projected CNY balance")}</p></div><span class="co-chart-key">${bi("当前计划", "Current plan")}</span></div><svg id="tf-chart" class="tf-chart" role="img" aria-label="${bi("企业未来56天人民币资金走势", "Company CNY cash forecast over 56 days")}"></svg><div class="co-events">${upcoming.map((event) => `<button type="button" data-cash-overview="${event.id}"><span class="co-event-date">${date(event.day)}</span><span>${bi(...event.label)}</span><strong class="${event.amount > 0 ? "in" : "out"}">${event.amount < 0 ? "−" : "+"}${money(event.amount)}</strong></button>`).join("")}</div><p class="tf-note">${bi("确认新的回款或付款资料后，订单、资金预测和 AI 分析同步更新。", "Confirmed receipt and payment records update orders, cash forecasts and AI context together.")}</p></section>`;
}

function companyDocuments() {
  return `${knowledge.view()}<details class="sx-details"><summary>${bi("按订单浏览资料", "Browse evidence by order")}</summary>${companyOrders("documents")}</details><details class="sx-details"><summary>${bi("企业共用资料", "Shared company records")}</summary><div class="sx-detail-content">${docTypes
    .filter((d) => d.scope === "company")
    .map(docRow)
    .join("")}</div></details>${activeJob() ? flowPanel() : ""}`;
}

function companyAi() {
  const turns = flow.chat.filter((t) => !t.archived && t.scope === "company");
  return `<section class="tx-chat"><div class="tx-chat-top"><span>${bi("企业整体资金 · 全部订单", "Company cash · All orders")}</span><button class="tf-link" data-action="ai-new">${bi("新对话", "New chat")}</button></div><div class="tx-messages" aria-live="polite">${turns.length ? conversationTurns(turns, (t) => t.rag ? ragReply(t) : `<div class="tx-chat-user" data-user-content>${escapeHtml(t.question)}</div><div class="tx-chat-reply"><span class="sx-eyebrow">CashWeave · ${bi("企业分析", "Company analysis")}${t.snapshot.v !== flow.version ? " · " + bi("较早资料", "Earlier evidence") : ""}</span><p>${bi(`当前人民币可用余额为 ${money(t.snapshot.opening)}，美元余额 USD 19,970 单独保留。根据已确认安排及预计回款，56 天最大资金缺口为 ${money(t.snapshot.peak)}。重点跟进 Harbour Supplies 的 USD 12,000 尾款${setupMode ? "。" : `，以及 Nordlicht 的 USD ${t.snapshot.feeRemaining ?? 30} 未结差额。`}`, `Available CNY is ${money(t.snapshot.opening)}; USD 19,970 remains separate. Based on the confirmed schedule and expected receipts, the 56-day peak shortfall is ${money(t.snapshot.peak)}. Follow up Harbour Supplies’ USD 12,000 balance${setupMode ? "." : ` and Nordlicht’s USD ${t.snapshot.feeRemaining ?? 30} outstanding difference.`}`)}${t.snapshot.partialReceipt ? `<br>${partialAnalysis(t.snapshot)}` : ""}</p></div>`) : `<div class="tx-chat-empty"><span class="sx-ai-mark">✦</span><h1>${bi("公司的资金，需要关注什么？", "What needs attention across the business?")}</h1><p>${bi("从整体现金情况开始，具体订单再展开。", "Start with company cash, then explore the relevant order.")}</p></div>`}</div><div class="tx-composer">${knowledge.composer()}<div class="tx-chat-hints" ${turns.length ? "hidden" : ""}><button data-fill-question="${bi("帮我概括公司的资金情况", "Summarize company cash and priorities")}">${bi("哪些付款需要先处理？", "Which payments need attention?")}</button></div><form id="tf-ai-form"><textarea id="tf-ai-question" rows="3" aria-label="${bi("向 AI 助手提问", "Ask CashWeave")}" placeholder="${bi("询问公司的资金和待处理事项…", "Ask about company cash and priorities…")}">${escapeHtml(state.aiDraft || "")}</textarea><div class="tx-send-row"><span class="tf-note">${bi("Enter 换行", "Enter for a new line")}</span><button class="tf-button primary" type="button" data-action="ai-submit">${bi("发送", "Send")} ↑</button></div></form></div></section><details class="sx-details"><summary>${bi("选择订单继续分析", "Explore an order")}</summary>${companyOrders("assistant")}</details>`;
}
root.addEventListener("click", (e) => {
  const cashEntry = e.target.closest("[data-cash-overview]");
  if (cashEntry) {
    const snapshot = enrich(currentBase());
    openCashMovement(cashEvents(snapshot).find(event => event.id === cashEntry.dataset.cashOverview), snapshot);
    return;
  }
  const entry = e.target.closest("[data-open-order]");
  if (!entry) return;
  selectCase(entry.dataset.openOrder);
  state.page = entry.dataset.orderDestination;
  state.delayed = false;
  state.extended = false;
  render();
  persist();
  window.scrollTo({ top: 0 });
});


function notificationText(item) {
  const copy = {
    evidence: ["新邮件需要你补充或确认", "New evidence needs your input", "已关联这笔订单，补齐金额、日期或核对字段后即可更新资金预测。", "Complete the amount and date or verify the fields to update the cash forecast."],
    updated: ["订单与资金预测已更新", "Order and cash forecast updated", `新确认的资料已同步，56 天最大资金缺口为 ${money(item.peak || 0)}。`, `Confirmed evidence is synced. The 56-day peak shortfall is ${money(item.peak || 0)}.`],
    cash: ["这笔订单需要安排付款", "This order needs a payment plan", `当前预测最大缺口 ${money(item.peak || 0)}。查看资金影响并准备下一步。`, `The current forecast shows a ${money(item.peak || 0)} peak gap. Review the impact and next steps.`],
    supplier: ["供应商付款临近", "Supplier payment is approaching", `${date(item.due)} 付款当天预计缺口 ${money(item.gap || 0)}，请协调分期或延期。`, `The payment on ${date(item.due)} has a projected ${money(item.gap || 0)} gap. Review split or deferred payment.`],
    receipt: ["到期核实客户回款", "Time to verify the buyer receipt", `预计回款日为 ${date(item.due)}。请补充最新银行流水核实到账。`, `The expected receipt date is ${date(item.due)}. Add a current bank record to verify arrival.`],
  }[item.kind];
  return { title: bi(copy[0], copy[1]), body: bi(copy[2], copy[3]) };
}

function renderNotifications() {
  state.followups ||= { day: 0, paused: [], read: [] };
  const view = followupView(flow, state.followups);
  const unread = view.items.filter(n => n.unread).length;
  $("#tx-notification-control").innerHTML = `<button class="nt-bell" data-notification="toggle" aria-label="${bi("消息提醒", "Notifications")}${unread ? ` (${unread})` : ""}" aria-expanded="${!!state.notificationsOpen}" aria-controls="tx-notification-panel"><i data-lucide="bell" aria-hidden="true"></i>${unread ? `<span class="nt-count">${unread}</span>` : ""}</button>`;
  $("#tx-notification-panel").setAttribute("aria-label", bi("消息与跟进", "Notifications and follow-up"));
  $("#tx-notification-panel").hidden = !state.notificationsOpen;
  if (!state.notificationsOpen) return;
  $("#tx-notification-panel").innerHTML = `<div class="nt-heading"><div><h2>${bi("消息与跟进", "Notifications & follow-up")}</h2><p>${bi("展开事件，查看影响与下一步。", "Select an event to review its impact and next step.")}</p></div><button class="tf-link" data-notification="close" aria-label="${bi("关闭消息提醒", "Close notifications")}">×</button></div><div class="nt-list">${view.items.map(item => {
    const t = notificationText(item), selected = state.notificationSelection === item.id;
    return `<div class="nt-event ${selected ? 'selected' : ''}"><button class="nt-item" data-notification-id="${item.id}" aria-expanded="${selected}" aria-controls="nt-detail-${item.id}"><span class="nt-meta">TF-26104 · ${item.trigger === 'time' ? bi('时间提醒', 'Scheduled reminder') : bi('业务更新', 'Business update')}</span><strong>${t.title}<span aria-hidden="true">${selected ? '−' : '+'}</span></strong></button>${selected ? `<section class="nt-detail" id="nt-detail-${item.id}" aria-label="${bi('事件详情','Event details')}"><p>${t.body}</p><dl><div><dt>${bi('关联客户','Customer')}</dt><dd>Harbour Supplies</dd></div><div><dt>${bi('下一步','Next step')}</dt><dd>${item.kind === 'evidence' ? bi('核对资料中的金额与日期','Review the amount and date') : item.kind === 'receipt' ? bi('上传银行流水，核实到账','Upload a bank record to verify receipt') : bi('查看资金缺口，制定付款安排','Review the cash gap and plan payments')}</dd></div></dl><div class="nt-actions"><button class="tf-button primary" data-notification="analyze" data-event-id="${item.id}">${bi('让 AI 分析','Analyze with AI')}</button><button class="tf-link" data-notification="order" data-event-id="${item.id}">${bi('查看订单','View order')} →</button></div></section>` : ''}</div>`;
  }).join('') || `<p class="nt-empty">${bi("当前没有待处理提醒。", "No alerts need attention.")}</p>`}</div><details class="nt-tracking" ${state.followupsExpanded ? "open" : ""}><summary>${bi("正在跟进的事项", "Scheduled follow-ups")} (${view.watches.filter(w => !w.paused).length})</summary>${view.watches.map(w => `<div class="nt-watch"><span>${w.id === 'supplier' ? bi('付款日前三天检查资金', 'Check cash three days before payment') : bi('预计回款日核实到账', 'Verify receipt on the expected date')}<small>${date(w.day)} · ${w.paused ? bi('已暂停','Paused') : bi('跟进中','Following')}</small></span><button class="tf-link" data-watch="${w.id}">${w.paused ? bi('恢复','Resume') : bi('暂停','Pause')}</button></div>`).join('')}<div class="nt-demo"><span>${bi('演示日期', 'Demo date')} ${date(state.followups.day)}</span>${view.next !== undefined ? `<button class="tf-link" data-notification="advance">${bi('推进至下一次提醒', 'Advance to next reminder')} →</button>` : ''}<small>${bi('本地演示按此日期检查提醒，关闭网页后不会后台运行。', 'Local demo checks use this date. No background execution after closing the page.')}</small></div></details>`;
}

root.addEventListener('click', event => {
  const b = event.target.closest('[data-notification],[data-notification-id],[data-watch]');
  if (!b) return;
  event.stopPropagation();
  const action = b.dataset.notification;
  if (action === 'advance' || b.dataset.watch) state.followupsExpanded = true;
  if (action === 'toggle') {
    state.notificationsOpen = !state.notificationsOpen;
    if (state.notificationsOpen) {
      const items = followupView(flow, state.followups).items;
      state.notificationSelection = items.find(item => item.unread)?.id || items[0]?.id;
      state.followups = markNotificationsRead(state.followups, items);
    }
  }
  if (action === 'close') state.notificationsOpen = false;
  if (action === 'advance') state.followups.day = followupView(flow, state.followups).next;
  if (b.dataset.watch) {
    const id = b.dataset.watch;
    state.followups.paused = state.followups.paused.includes(id) ? state.followups.paused.filter(x => x !== id) : [...state.followups.paused, id];
  }
  if (b.dataset.notificationId) {
    state.notificationSelection = state.notificationSelection === b.dataset.notificationId ? null : b.dataset.notificationId;
  }
  if (action === 'order' || action === 'analyze') {
    const item = followupView(flow, state.followups).items.find(n => n.id === b.dataset.eventId);
    state.followups = markNotificationsRead(state.followups, [item]);
    state.notificationsOpen = false;
    selectCase('buyer');
    state.delayed = false; state.extended = false;
    if (action === 'analyze') {
      state.page = 'assistant';
      const text = notificationText(item);
      askAi(bi(`请跟进订单 TF-26104（Harbour Supplies）的提醒「${text.title}」：${text.body} 请分析资金影响和下一步。`, `Follow up order TF-26104 (Harbour Supplies): ${text.title}. ${text.body} Explain the cash impact and next action.`), 'buyer');
      flow.chat.at(-1).followupType = item.kind;
    } else {
      const pending = activeJob() && activeJob().status !== 'confirmed';
      setOrderStep(pending ? 2 : activeJob() ? 3 : 1);
    }
    window.scrollTo({ top: 0 });
  }
  render(); persist();
  if (state.notificationsOpen && ['toggle','advance'].includes(action)) $("#tx-notification-panel").focus();
  if (action === 'close') $(".nt-bell").focus();
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && state.notificationsOpen) {
    state.notificationsOpen = false; render(); $(".nt-bell").focus();
  }
});
document.addEventListener('click', event => {
  if (state.notificationsOpen && !event.target.closest('#tx-notification-control,#tx-notification-panel')) {
    state.notificationsOpen = false; renderNotifications(); renderIcons(root);
  }
});
