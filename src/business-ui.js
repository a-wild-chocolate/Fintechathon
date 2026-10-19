import {configureKnowledgeCompany, knowledgeAPI, createKnowledgeUI, askKnowledge, watchAgentRun} from './knowledge.js';
import {setupChat, rememberChatScroll, replaceChatReply} from './chat-ui.js';
import {collectHumanAnswers, humanReplySummary} from './human-loop.js';
import {attachCashChart} from './cash-chart.js';

const root=document.getElementById('tradeflow-export-preview');
const params=new URLSearchParams(location.search), companyId=params.get('company');
configureKnowledgeCompany(companyId);
const esc=value=>String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const amount=(value,currency='CNY')=>new Intl.NumberFormat('en',{style:'currency',currency,maximumFractionDigits:2}).format(value);
let lang=params.get('lang') || localStorage.getItem('cashweave-language') || 'en';
const tr=(zh,en)=>lang==='zh'?zh:en;
let companies=[],business=null,page=companyId?'overview':'companies',selectedOrder='',selectedDocument='',draft='',chat=[],sessions={};
let form=null,review=null,error='',busy=false,saveStatus='',agentEnabled=false,viewRevision=0,saveTimer,pendingView,saving=false;
const monitors=new Set();
const currentOrder=()=>business?.snapshot.orders.find(o=>o.id===selectedOrder);
const taskToOpen=()=>chat.find(t=>t.rag.status==='pending') || chat.findLast(t=>t.read===false);
const taskLabel=()=>chat.some(t=>t.rag.status==='pending')?tr('AI 正在后台分析 · 查看','AI is analyzing · View'):tr('AI 分析已完成 · 查看结果','AI analysis ready · View result');
const post=body=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const knowledge=createKnowledgeUI({root,language:()=>lang,order:()=>selectedOrder,orders:()=>business?.snapshot.orders || [],
  selectedDocument:()=>selectedDocument,rerender:render,
  selectDocument:(doc,openChat)=>{selectedDocument=doc?.id || '';if(openChat){selectedOrder=doc.metadata.order_id || '';page='assistant';draft=tr('读取这份付款资料，提取金额和日期；缺失的字段请向我提问。','Read this payment document, extract the amount and date, and ask for missing fields.');}render();saveView();}});
const statusName=s=>({preparing:tr('备货中','Preparing'),shipped:tr('已发运','Shipped'),completed:tr('已完成','Completed'),cancelled:tr('已取消','Cancelled')})[s];
function goCompany(id){location.href='/?company='+encodeURIComponent(id)+'&lang='+lang;}
function selectOrder(id){selectedOrder=id;selectedDocument='';page='order';render();saveView();}
function notice(message){error=message;const host=root.querySelector('#business-error');if(host){host.hidden=!error;host.textContent=error;}}
function updateSaveStatus(message){saveStatus=message;const node=root.querySelector('#business-save');if(node)node.textContent=message;}
function viewPayload(){return {lang,selectedOrder,selectedDocument,draft,chat,sessions};}
function saveView(){
  if(!companyId)return;
  pendingView=structuredClone(viewPayload());clearTimeout(saveTimer);saveTimer=setTimeout(flushView,400);
}
async function flushView(){
  if(saving || !pendingView)return;
  saving=true;const workspace=pendingView;pendingView=null;updateSaveStatus(tr('正在保存…','Saving…'));
  try{const response=await knowledgeAPI('/business/view',{...post({revision:viewRevision,workspace}),method:'PUT'});viewRevision=response.revision;updateSaveStatus(tr('已保存','Saved'));}
  catch(e){notice(e.message);updateSaveStatus(tr('未保存','Not saved'));pendingView=null;}
  finally{saving=false;if(pendingView)await flushView();}
}
async function refreshBusiness(){business=await knowledgeAPI('/business/overview');}
function head(title,sub,action=''){return `<div class="business-heading"><div><h1>${title}</h1><p>${sub}</p></div>${action}</div>`;}
function field(name,label,value='',type='text',extra=''){return `<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`;}
function numberField(name,label,value=0,extra=''){return field(name,label,value,'number',`min="0" step="0.01" required ${extra}`);}
function orderRows(){
  const orders=business.snapshot.orders;
  if(!orders.length)return `<div class="business-empty"><h2>${tr('先添加第一笔订单','Add your first order')}</h2><p>${tr('录入回款和供应商付款计划，即可看到资金变化。','Add the receipt and supplier payment plan to see its cash impact.')}</p></div>`;
  return `<div class="business-list">${orders.map(o=>`<button class="business-order" data-order="${esc(o.id)}"><div><strong>${esc(o.customer)}</strong><small>${esc(o.id)} · ${esc(o.goods)} · ${statusName(o.status)}</small></div><div><strong>${amount(o.total-o.received-o.adjustment,o.currency)}</strong><small>${tr('未结余额','Outstanding')} · ${o.receipt_date || tr('回款日期未定','Receipt date unknown')}</small></div><span>›</span></button>`).join('')}</div>`;
}
function companyList(){return head(tr('企业工作台','Your companies'),tr('选择企业，或从空账本创建新的企业。','Choose a company or start with an empty workspace.'),`<button class="tf-button primary" data-new-company>${tr('新增企业','New company')}</button>`)+`<div class="business-list">${companies.map(c=>`<button class="business-order" data-company="${esc(c.id)}"><div><strong>${esc(c.name)}</strong><small>${esc(c.country)} · ${tr('余额截至','Balances as of')} ${c.planning_start}</small></div><span>→</span></button>`).join('') || `<p class="business-empty">${tr('还没有企业。添加名称和期初余额即可开始。','No companies yet. Add a name and opening balances to begin.')}</p>`}</div><p class="business-secondary"><a href="/?demo=1&lang=${lang}">${tr('打开原演示工作台','Open the original demo workspace')}</a></p>`;}
function dashboard(){
  const {snapshot:s,cash:c}=business;
  const usd=s.accounts.filter(a=>a.currency==='USD').reduce((sum,a)=>sum+a.opening_minor/100,0);
  return head(esc(business.company.name),tr('从公司资金出发，找到需要处理的订单。','Understand your cash position, then act on an order.'),`<button class="tf-button primary" data-new-order>${tr('新增订单','New order')}</button>`)+`
  <section class="business-balances"><div><span>${tr('人民币期初余额','Opening CNY')}</span><strong>${amount(s.opening)}</strong><small>${s.planning_start}</small></div><div><span>${tr('美元期初余额','Opening USD')}</span><strong>${amount(usd,'USD')}</strong><small>${tr('未自动计入人民币预测','Not automatically converted to CNY')}</small></div><div><span>${tr('56 天预计最大缺口','56-day peak shortfall')}</span><strong class="${c.peak_shortfall_cny?'business-risk':''}">${amount(c.peak_shortfall_cny)}</strong><small>${c.first_shortfall ? tr('首次出现：','First gap: ')+c.first_shortfall.date : tr('当前计划下无缺口','No gap in the current plan')}</small></div></section>
  ${c.peak_shortfall_cny?`<div class="business-insight"><span>${tr('有付款早于回款，需要协调资金安排。','Some payments precede receipts. Review the funding gap.')}</span><button class="tf-link" data-company-analysis>${tr('让 AI 分析','Analyze with AI')} ↗</button></div>`:''}
  <div class="business-section-title"><h2>${tr('订单','Orders')} <small>${s.orders.length}</small></h2></div>${orderRows()}
  <section class="business-chart"><div class="business-section-title"><h2>${tr('资金走势','Cash outlook')}</h2><small>${tr('按已确认计划计算 · CNY','Saved plans · CNY')}</small></div><svg id="business-chart" class="tf-chart"></svg></section>
  ${c.outside_horizon.length?`<p class="tf-note">${tr('以下收付款不在本次 56 天预测内：','Outside the 56-day forecast: ')}${c.outside_horizon.map(m=>esc(m.order_id || m.label)+' · '+m.due_date).join(', ')}</p>`:''}`;
}
function details(){
  const o=currentOrder();if(!o)return dashboard();
  const rows=[[tr('客户','Customer'),o.customer],[tr('货物','Goods'),o.goods],[tr('订单总额','Order value'),amount(o.total,o.currency)],
    [tr('已收金额','Already received'),amount(o.received,o.currency)],[tr('未结余额','Outstanding'),amount(o.total-o.received-o.adjustment,o.currency)],
    [tr('下次预计回款','Next expected receipt'),amount(o.expected,o.currency)+' · '+(o.receipt_date || tr('未定','Unscheduled'))],
    [tr('结汇假设','Conversion assumption'),`1 ${o.currency} = ${o.fx_rate} CNY`],
    [tr('供应商待付','Supplier payment'),amount(o.supplier_amount)+' · '+(o.supplier_date || tr('未定','Unscheduled'))]];
  return head(esc(o.id)+' · '+esc(o.customer),statusName(o.status),`<button class="tf-button" data-edit-order>${tr('编辑订单','Edit order')}</button>`)+
    `<div class="business-next"><div><h2>${tr('查看这笔订单对公司资金的影响','See how this order affects company cash')}</h2><p>${tr('先补充依据，再由 AI 分析回款安排与资金缺口。','Add the evidence, then ask AI to review receipts and funding needs.')}</p></div><button class="tf-button primary" data-order-analysis>${tr('分析资金影响','Analyze cash impact')} ↗</button></div>
    <dl class="business-facts">${rows.map(([a,b])=>`<div><dt>${a}</dt><dd>${esc(b)}</dd></div>`).join('')}</dl><div class="business-section-title"><h2>${tr('关联资料','Order evidence')}</h2><button class="tf-link" data-page="documents">${tr('上传或查看资料','Upload or view documents')} →</button></div><p class="tf-note">${tr('资料将关联此订单，AI 可检索原文并显示引用。','Documents are linked to this order and available to AI with source citations.')}</p>`;
}
function scopeSelector(){return `<label class="business-scope">${tr('分析范围','Scope')}<select id="business-order-scope"><option value="">${tr('企业整体','Whole company')}</option>${business.snapshot.orders.map(o=>`<option value="${esc(o.id)}" ${o.id===selectedOrder?'selected':''}>${esc(o.id)} · ${esc(o.customer)}</option>`).join('')}</select></label>`;}
function turnHTML(t){return `<div class="tx-chat-user" data-user-content>${esc(t.question)}</div><div class="tx-chat-reply" data-reply-id="${t.id}" data-chat-status="${t.rag.status}"><span class="sx-eyebrow">CashWeave</span>${knowledge.answer(t)}</div>`;}
function chatPage(){
  const turns=chat.filter(t=>t.orderId===selectedOrder && !t.archived);
  turns.filter(t=>t.rag.status!=='pending').forEach(t=>t.read=true);
  return `<section class="tx-chat"><div class="tx-chat-top">${scopeSelector()}<button class="tf-link" data-new-chat>${tr('新对话','New chat')}</button></div><div class="tx-messages">${turns.map(turnHTML).join('') || `<div class="tx-chat-empty"><h1>${tr('这笔生意，下一步怎么安排？','What should we do next?')}</h1><p>${tr('结合当前企业账本和资料，分析回款、付款与资金缺口。','Analyze receipts, payments and funding using your saved business records.')}</p></div>`}</div><div class="tx-composer">${knowledge.composer()}<div class="tx-chat-hints" ${turns.length?'hidden':''}><button data-fill>${tr('帮我分析资金安排','Analyze the cash plan')}</button></div><form id="tf-ai-form"><textarea id="tf-ai-question" aria-label="${tr('向 AI 提问','Ask CashWeave')}">${esc(draft)}</textarea><div class="tx-send-row"><span class="tf-note">${tr('Enter 发送 · Shift + Enter 换行','Enter to send · Shift + Enter for a new line')}</span><button type="button" class="tf-button primary" data-action="ai-submit">↑</button></div></form></div></section>`;
}
function formPage(){
  const data=form.data;
  if(form.kind==='company')return head(tr('新增企业','New company'),tr('填写真实业务名称与同一日期的期初余额。','Enter your business name and balances as of one date.'))+`<form id="business-form" class="business-form"><fieldset><legend>${tr('企业信息','Company')}</legend>${field('name',tr('企业名称','Company name'),data.name,'text','required maxlength="160"')}${field('country',tr('国家代码','Country code'),data.country || 'CN','text','required minlength="2" maxlength="2"')}${field('planning_start',tr('余额截至日期','Balance date'),data.planning_start,'date','required')}</fieldset><fieldset><legend>${tr('期初资金','Opening balances')}</legend>${numberField('opening_cny',tr('人民币余额 · CNY','CNY balance'),data.opening_cny)}${numberField('opening_usd',tr('美元余额 · USD','USD balance'),data.opening_usd)}</fieldset>${formActions()}</form>`;
  const currencies=['USD','CNY','EUR','GBP'];
  return head(form.create?tr('新增订单','New order'):tr('编辑订单','Edit order'),tr('录入业务安排，下一步核对资金影响。','Enter the business plan, then review its cash impact.'))+`<form id="business-form" class="business-form"><fieldset><legend>${tr('订单信息','Order')}</legend>${field('id',tr('订单号','Order number'),data.id,'text',`required pattern="[A-Za-z0-9_-]+" ${form.create?'':'readonly'}`)}${field('customer',tr('客户名称','Customer'),data.customer,'text','required')}${field('country',tr('客户国家或地区','Customer country'),data.country)}${field('goods',tr('货物','Goods'),data.goods,'text','required')}<label>${tr('币种','Currency')}<select name="currency">${currencies.map(c=>`<option ${data.currency===c?'selected':''}>${c}</option>`).join('')}</select></label><label>${tr('状态','Status')}<select name="status">${['preparing','shipped','completed','cancelled'].map(s=>`<option value="${s}" ${data.status===s?'selected':''}>${statusName(s)}</option>`).join('')}</select></label>${numberField('total',tr('订单总额','Order value'),data.total)}${numberField('received',tr('已收金额（已计入期初资金）','Already received (included in opening balances)'),data.received)}</fieldset>
  <fieldset><legend>${tr('回款计划','Receipt plan')}</legend><p>${tr('只填写已明确的部分。日期未知时，预计金额填 0，余款暂不计入资金预测。','Enter the known portion. If its date is unknown, use 0 expected; the remainder stays unscheduled.')}</p>${numberField('expected',tr('下次预计收款金额','Next expected amount'),data.expected)}${field('receipt_date',tr('预计人民币可用日','Expected CNY availability date'),data.receipt_date,'date')}${field('fx_rate',tr('每单位外币可兑换的人民币','CNY per unit of order currency'),data.fx_rate,'number','min="0.000001" max="1000" step="0.000001" required')}<p>${tr('汇率为计划假设，人民币订单固定为 1；这里不会进行真实结汇。','This is a planning rate. CNY orders use 1; no currency exchange is executed.')}</p></fieldset>
  <fieldset><legend>${tr('供应商付款','Supplier payment')}</legend>${field('supplier',tr('供应商','Supplier'),data.supplier)}${numberField('supplier_amount',tr('尚需支付金额 · CNY','Amount still payable · CNY'),data.supplier_amount)}${field('supplier_date',tr('到期日','Due date'),data.supplier_date,'date')}</fieldset>${formActions()}</form>`;
}
function formActions(){return `<div class="business-actions"><button type="button" class="tf-link" data-cancel-form>${tr('取消','Cancel')}</button><button class="tf-button primary" ${busy?'disabled':''}>${busy?tr('正在计算…','Calculating…'):tr('核对并继续','Review and continue')} →</button></div>`;}
function reviewPage(){
  const d=review.data;const company=form.kind==='company';
  const rows=company?[[tr('企业名称','Company'),d.name],[tr('国家','Country'),d.country],[tr('余额日期','Balance date'),d.planning_start],[tr('人民币余额','CNY balance'),amount(d.opening_cny)],[tr('美元余额','USD balance'),amount(d.opening_usd,'USD')]]:
    [[tr('订单','Order'),d.id],[tr('客户','Customer'),d.customer],[tr('货物','Goods'),d.goods],[tr('状态','Status'),statusName(d.status)],[tr('订单金额 / 已收','Order value / received'),amount(d.total,d.currency)+' / '+amount(d.received,d.currency)],
     [tr('预计回款','Expected receipt'),amount(d.expected,d.currency)+' · '+(d.receipt_date || tr('未定','Unscheduled'))],[tr('结汇假设','Conversion assumption'),`1 ${d.currency} = ${d.fx_rate} CNY`],
     [tr('供应商 / 付款','Supplier / payment'),d.supplier+' · '+amount(d.supplier_amount)+' · '+(d.supplier_date || '—')]];
  return head(tr('确认后保存','Confirm and save'),tr('核对以下信息。确认前不会改变账本。','Review these details. The ledger changes only after confirmation.'))+`<dl class="business-facts">${rows.map(([a,b])=>`<div><dt>${a}</dt><dd>${esc(b)}</dd></div>`).join('')}</dl>${company?'':`<div class="business-impact"><strong>${tr('公司 56 天最大资金缺口','Company 56-day peak shortfall')}</strong><span>${amount(review.before.peak_shortfall_cny)} → ${amount(review.after.peak_shortfall_cny)}</span><p>${review.after.first_shortfall?tr('首次缺口：','First gap: ')+review.after.first_shortfall.date:tr('当前计划下无资金缺口。','No shortfall under the updated plan.')}</p>${review.after.outside_horizon.length?`<p>${tr('部分收付款在 56 天范围外，不计入本图。','Some cash movements fall outside the 56-day forecast.')}</p>`:''}</div>`}<div class="business-actions"><button class="tf-link" data-back-form>${tr('返回修改','Back to edit')}</button><button class="tf-button primary" data-confirm-save ${busy?'disabled':''}>${busy?tr('正在保存…','Saving…'):tr('确认并保存','Confirm and save')}</button></div>`;
}
function drawChart(){
  const svg=root.querySelector('#business-chart');if(!svg)return;
  const points=business.cash.daily_balances.map((r,d)=>({d,v:r.balance_cny}));const width=Math.max(360,svg.parentElement.clientWidth),height=250;
  const min=Math.min(0,...points.map(p=>p.v)),max=Math.max(1,...points.map(p=>p.v));
  const x=d=>60+d/55*(width-80),y=v=>20+(max-v)/(max-min)*(height-55);
  svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.setAttribute('aria-label',tr('56 天人民币资金预测','56-day CNY cash forecast'));
  const path=points.map((p,i)=>`${i?'H':'M'}${x(p.d)}${i?'V':','}${y(p.v)}`).join(' ');
  svg.innerHTML=`${[max,0,min].filter((v,i,a)=>a.indexOf(v)===i).map(v=>`<line x1="60" x2="${width-20}" y1="${y(v)}" y2="${y(v)}" stroke="#dce7e3"/><text x="0" y="${y(v)+4}" fill="#698078" font-size="11">${Math.round(v/1000)}k</text>`).join('')}<path d="${path}" fill="none" stroke="#167669" stroke-width="2.5"/>${[0,27,55].map(d=>`<text x="${x(d)}" y="247" text-anchor="${d===55?'end':'start'}" fill="#698078" font-size="11">${business.cash.daily_balances[d].date}</text>`).join('')}`;
  attachCashChart(svg,{snapshot:business.snapshot,points,baseline:points,comparisonLabel:'Current',language:lang,x,y,width,height,
    onSelect:event=>{selectedOrder=event.orderId || '';page=selectedOrder?'order':'assistant';draft=tr('分析这笔收付款对公司资金的影响：','Analyze the company cash impact of: ')+event.label[1];render();saveView();}});
}
function render(){
  rememberChatScroll(root);root.dataset.page=page==='assistant'?'assistant':'home';root.lang=lang==='zh'?'zh-CN':'en';root.setAttribute('aria-label',tr('CashWeave 小微出口企业财务工作台','CashWeave export finance workspace'));
  const views={companies:companyList,overview:dashboard,orders:()=>head(tr('订单','Orders'),tr('所有客户与收付款安排。','Customers and their payment plans.'),`<button class="tf-button primary" data-new-order>${tr('新增订单','New order')}</button>`)+orderRows(),order:details,documents:()=>scopeSelector()+knowledge.view(),assistant:chatPage,form:formPage,review:reviewPage};
  root.innerHTML=`<header class="tf-top"><a class="business-brand" href="/">↗ CashWeave</a><span class="tf-company">${esc(business?.company.name || tr('企业工作台','Business workspace'))}</span><div class="business-top-actions">${companyId?`<a href="/?lang=${lang}">${tr('切换企业','Switch company')}</a>`:''}<button class="tf-link" data-language>${lang==='en'?'中文':'English'}</button><small id="business-save">${esc(saveStatus)}</small></div></header><div class="tf-body">${companyId?`<nav class="tf-nav">${[['overview',tr('资金总览','Overview')],['orders',tr('订单','Orders')],['documents',tr('资料库','Documents')],['assistant',tr('AI 助手','AI assistant')]].map(([id,label])=>`<button data-page="${id}" ${page===id?'aria-current="page"':''}>${label}</button>`).join('')}</nav>`:''}<main class="tf-main business-main"><p id="business-error" role="alert" class="business-error" ${error?'':'hidden'}>${esc(error)}</p>${business || !companyId?views[page]():tr('正在加载…','Loading…')}</main></div><div class="business-running" ${taskToOpen()?'':'hidden'}><button class="tf-link" data-active-run>${taskLabel()}</button></div>`;
  setupChat(root,lang,companyId+':'+selectedOrder);drawChart();
}
function newOrder(){form={kind:'order',create:true,data:{id:'',customer:'',country:'',goods:'',currency:'USD',total:'',received:0,expected:0,receipt_date:'',fx_rate:'',supplier:'',supplier_amount:0,supplier_date:'',status:'preparing',version:business.snapshot.version}};review=null;page='form';render();}
function analysisQuestion(){return selectedOrder?tr(`分析订单 ${selectedOrder} 对公司资金的影响，并给出下一步建议。`,`Analyze order ${selectedOrder}'s impact on company cash and recommend next steps.`):tr('分析公司资金缺口及应优先处理的订单。','Analyze company cash gaps and prioritize the orders needing action.');}
async function startChat(question=draft){
  question=question.trim();if(!question || chat.some(t=>t.rag.status==='pending'&&t.orderId===selectedOrder))return;
  const turn={id:crypto.randomUUID(),question,orderId:selectedOrder,documentId:selectedDocument,language:lang,read:false,rag:{status:'pending'}};
  chat.push(turn);draft='';page='assistant';render();saveView();await runTurn(turn);
}
async function runTurn(turn){
  if(monitors.has(turn.id))return;monitors.add(turn.id);
  const onProgress=progress=>{turn.rag.progress=progress;knowledge.updateProgress(turn);saveView();};
  try{
    const key=JSON.stringify([turn.orderId,turn.documentId]);
    const result=turn.rag.progress?.run_id?await watchAgentRun(turn.rag.progress.run_id,onProgress):await askKnowledge({question:turn.question,language:turn.language,order_id:turn.orderId,document_id:turn.documentId,session_id:sessions[key] || null,live:agentEnabled,onProgress,history:[]});
    if(result.session_id)sessions[key]=result.session_id;
    turn.rag={...result,status:'done'};await refreshBusiness();
  }catch(e){turn.rag={status:'error',error:e.message,progress:turn.rag.progress};}
  monitors.delete(turn.id);
  if(page==='assistant' && selectedOrder===turn.orderId)turn.read=true;
  saveView();
  const running=root.querySelector('.business-running');if(running){running.hidden=!taskToOpen();running.querySelector('button').textContent=taskLabel();}
  if(page==='assistant' && selectedOrder===turn.orderId){if(!replaceChatReply(root,turn,turnHTML(turn),lang))render();}
  else if(['overview','order'].includes(page))render();
}
async function answerHuman(turn,skip){
  if(turn.rag.human_response)return;
  const answers=collectHumanAnswers(turn,skip);
  const response=await knowledgeAPI(`/agents/runs/${turn.rag.run_id}/answers`,post({answers,language:lang}));turn.rag.human_response=response;
  const next={id:crypto.randomUUID(),question:humanReplySummary(response,lang),orderId:turn.orderId,documentId:turn.documentId,language:lang,read:false,rag:{status:'pending',progress:response}};
  chat.push(next);render();saveView();await runTurn(next);
}
root.addEventListener('input',e=>{
  if(e.target.id==='tf-ai-question'){draft=e.target.value;saveView();}
  const human=e.target.closest('[data-human-form]');if(!human)return;
  const turn=chat.find(t=>t.id===human.dataset.humanForm),id=e.target.dataset.humanQuestion || e.target.dataset.humanComment;
  if(id){turn.humanDraft ||= {};turn.humanDraft[id] ||= {};turn.humanDraft[id][e.target.dataset.humanQuestion?'choice':'comment']=e.target.value;saveView();}
});
root.addEventListener('change',e=>{
  if(e.target.name==='currency' && e.target.value==='CNY')root.querySelector('[name=fx_rate]').value='1';
  if(e.target.id==='business-order-scope'){selectedOrder=e.target.value;selectedDocument='';render();saveView();}
});
root.addEventListener('toggle',e=>{if(e.target.matches('.kb-progress')){const t=chat.find(t=>t.id===e.target.closest('[data-progress-turn]').dataset.progressTurn);t.progressOpen=e.target.open;saveView();}},true);
root.addEventListener('submit',async e=>{
  if(e.target.id==='tf-ai-form'){e.preventDefault();await startChat();return;}
  if(e.target.matches('[data-human-form]')){e.preventDefault();try{await answerHuman(chat.find(t=>t.id===e.target.dataset.humanForm),false);}catch(ex){notice(ex.message);}return;}
  if(e.target.getAttribute('id')!=='business-form')return;e.preventDefault();if(busy)return;
  const data=Object.fromEntries(new FormData(e.target));form.data=data;busy=true;error='';
  try{
    if(form.kind==='order'){
      for(const key of ['total','received','expected','fx_rate','supplier_amount'])data[key]=Number(data[key]);
      data.receipt_date ||= null;data.supplier_date ||= null;data.version=form.version ?? business.snapshot.version;
      if(data.currency==='CNY')data.fx_rate=1;
      const result=await knowledgeAPI('/business/orders/preview?create='+form.create,post(data));review={data,...result};
    }else review={data};
    page='review';
  }catch(ex){error=ex.message;}
  busy=false;render();
});
root.addEventListener('click',async e=>{
  const b=e.target.closest('button');if(!b)return;
  try{
    if(b.hasAttribute('data-language')){lang=lang==='en'?'zh':'en';localStorage.setItem('cashweave-language',lang);render();saveView();}
    if(b.dataset.company)goCompany(b.dataset.company);
    if(b.dataset.order)selectOrder(b.dataset.order);
    if(b.dataset.page){page=b.dataset.page;error='';if(page==='overview'||page==='orders')selectedOrder='';render();saveView();}
    if(b.hasAttribute('data-new-company')){form={kind:'company',data:{name:'',country:'CN',planning_start:new Date().toISOString().slice(0,10),opening_cny:0,opening_usd:0}};page='form';render();}
    if(b.hasAttribute('data-new-order'))newOrder();
    if(b.hasAttribute('data-edit-order')){form={kind:'order',create:false,version:business.snapshot.version,data:{...currentOrder()}};review=null;page='form';render();}
    if(b.hasAttribute('data-cancel-form')){page=companyId?'overview':'companies';form=null;review=null;error='';render();}
    if(b.hasAttribute('data-back-form')){page='form';error='';render();}
    if(b.hasAttribute('data-confirm-save')&&!busy){
      busy=true;render();
      try{
        if(form.kind==='company'){const result=await knowledgeAPI('/companies',post(review.data));goCompany(result.company.id);return;}
        business=await knowledgeAPI('/business/orders'+(form.create?'':'/'+encodeURIComponent(review.data.id)),{...post(review.data),method:form.create?'POST':'PUT'});
        selectedOrder=review.data.id;form=null;review=null;page='order';error='';updateSaveStatus(tr('已保存到数据库','Saved to database'));saveView();
      }finally{busy=false;render();}
    }
    if(b.hasAttribute('data-company-analysis')){selectedOrder='';selectedDocument='';await startChat(analysisQuestion());}
    if(b.hasAttribute('data-order-analysis')){selectedDocument='';await startChat(analysisQuestion());}
    if(b.hasAttribute('data-fill')){draft=analysisQuestion();render();root.querySelector('#tf-ai-question').focus();}
    if(b.dataset.action==='ai-submit')await startChat();
    if(b.hasAttribute('data-new-chat')){chat.filter(t=>t.orderId===selectedOrder&&t.rag.status!=='pending').forEach(t=>t.archived=true);sessions={};draft='';render();saveView();}
    if(b.hasAttribute('data-active-run')){const t=taskToOpen();selectedOrder=t.orderId;selectedDocument=t.documentId;t.archived=false;page='assistant';render();saveView();}
    if(b.dataset.kbCite){const [id,ref]=b.dataset.kbCite.split(':');const source=chat.find(t=>t.id===id).rag.sources.find(s=>s.id===Number(ref));await knowledge.open(source.document_id,source.version,source);}
    if(b.dataset.kbRetry){const t=chat.find(t=>t.id===b.dataset.kbRetry);t.rag.status='pending';render();await runTurn(t);}
    if(b.dataset.humanSkip)await answerHuman(chat.find(t=>t.id===b.dataset.humanSkip),true);
    if(b.dataset.agentConfirm){b.disabled=true;const result=await knowledgeAPI('/agents/proposals/'+b.dataset.agentConfirm+'/confirm',post({}));chat.filter(t=>t.rag.proposal?.id===result.proposal_id).forEach(t=>{t.rag.proposal.status='confirmed';});await refreshBusiness();render();saveView();await startChat(tr('已确认付款计划，请分析更新后的资金影响。','The payment plan is confirmed. Analyze the updated cash impact.'));}
  }catch(ex){notice(ex.message);}
});
try{
  if(companyId){
    const [data,view,status]=await Promise.all([knowledgeAPI('/business/overview'),knowledgeAPI('/business/view'),knowledgeAPI('/agents/status')]);business=data;viewRevision=view.revision;agentEnabled=status.mode==='multi_agent';
    if(view.workspace){({selectedOrder='',selectedDocument='',draft='',chat=[],sessions={}}=view.workspace);lang=params.get('lang') || view.workspace.lang || lang;}
    render();knowledge.refresh();setInterval(()=>knowledge.refresh(),4000);
    for(const t of chat.filter(t=>t.rag.status==='pending')){if(t.rag.progress?.run_id)runTurn(t);else{t.rag={status:'error',error:tr('请求尚未发出，请重新提问。','The request was not dispatched. Please try again.')};}}
  }else{companies=await knowledgeAPI('/companies');render();}
}catch(ex){error=ex.message;render();}
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')flushView();});
