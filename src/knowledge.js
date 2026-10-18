const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeURL = value => /^https?:\/\//i.test(value || '') || /^\/api\//.test(value || '') ? escape(value) : '';
export async function knowledgeAPI(path, options = {}) {
  const response = await fetch('/api' + path, options);
  const result = await response.json();
  if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : 'Request failed');
  return result;
}
const post = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export function createKnowledgeUI({ root, language, order, selectDocument, selectedDocument, rerender }) {
  let documents = [], status = null, error = '', notice = '', filter = 'private', query = '', uploading = false;
  const tr = (zh, en) => language() === 'en' ? en : zh;
  const processing = d => !['ready', 'lexical_ready', 'failed', 'embedding_failed'].includes(d.status);
  const labels = {
    queued: ['排队中', 'Queued'], running: ['解析中', 'Processing'], parsing: ['解析中', 'Parsing'],
    ready: ['可检索', 'Searchable'], lexical_ready: ['关键词可检索', 'Keyword searchable'],
    failed: ['处理失败', 'Processing failed'], embedding_failed: ['向量失败 · 关键词可用', 'Embedding failed · Keyword ready'],
  };
  const statusLabel = d => tr(...(labels[d.status] || ['处理中', 'Processing']));
  const title = d => language() === 'en' ? d.metadata.title_en || d.title : d.title;
  function visibleDocs() {
    return documents.filter(d => (filter === 'public' ? d.tenant === 'public' : d.tenant !== 'public') &&
      (!order() || d.tenant === 'public' || !d.metadata.order_id || d.metadata.order_id === order()) &&
      (!query || (d.title + ' ' + (d.metadata.title_en || '') + ' ' + (d.metadata.order_id || '')).toLowerCase().includes(query.toLowerCase())));
  }
  function rows() {
    const docs = visibleDocs();
    return `<div class="kb-status" role="status">${escape(error || notice || (status ? tr(`${status.documents} 份资料已连接`, `${status.documents} documents connected`) : tr('正在连接知识库…', 'Connecting to the library…')))}</div>
      ${docs.length ? docs.map(d => `<article class="kb-document"><div><button class="kb-title" data-kb-open="${d.id}" data-user-content>${escape(title(d))}</button><p>${escape(d.tenant === 'public' ? tr('公共政策', 'Public policy') : d.metadata.order_id || tr('企业共用', 'Company-wide'))} · v${d.current_version || d.latest_version} · <span class="${processing(d) ? 'kb-working' : ''}">${statusLabel(d)}</span></p></div><button class="tf-link" data-kb-ask="${d.id}" ${!d.current_version ? 'disabled' : ''}>${tr('向 AI 提问', 'Ask AI')} ↗</button></article>`).join('') : `<p class="kb-empty">${tr('这里还没有资料。上传邮件、合同或条款，索引完成后即可提问。', 'No documents here yet. Upload an email, contract or terms, then ask about it once indexed.')}</p>`}`;
  }
  function view() {
    return `<section class="tf-panel kb-library" data-user-content><div class="kb-heading"><div><span class="sx-eyebrow">${tr('资料 → 检索 → 引用', 'DOCUMENTS → RETRIEVAL → SOURCES')}</span><h2>${tr('让资料进入分析', 'Bring evidence into the conversation')}</h2><p>${tr('上传一次，订单和助手共用；回答可追溯到文件原文。', 'Upload once, use across orders and conversations, and trace answers to their sources.')}</p></div><a class="tf-link" href="/knowledge?lang=${language()}" target="_blank" rel="noopener">${tr('知识库工作台', 'Library workbench')} ↗</a></div>
      <form id="kb-upload-form" class="kb-upload"><label>${tr('资料文件', 'Document')}<input id="kb-file" type="file" accept=".txt,.md,.eml,.pdf,.docx,.csv,.xlsx,.json" required></label><label>${tr('归属订单', 'Link to order')}<select id="kb-order"><option value="">${tr('企业共用', 'Company-wide')}</option><option value="TF-26104" ${order() === 'TF-26104' ? 'selected' : ''}>TF-26104 · Harbour Supplies</option><option value="TF-26091" ${order() === 'TF-26091' ? 'selected' : ''}>TF-26091 · Nordlicht</option></select></label><button class="tf-button primary" ${uploading ? 'disabled' : ''}>${uploading ? tr('正在上传…', 'Uploading…') : tr('上传资料', 'Upload document')}</button></form><p class="tf-note">${tr('TXT / EML / PDF / DOCX / CSV / XLSX / MD / JSON · 后台解析，扫描件需 OCR', 'TXT / EML / PDF / DOCX / CSV / XLSX / MD / JSON · Background indexing; scanned files need OCR')}</p>
      <div class="kb-toolbar"><div class="kb-tabs"><button data-kb-filter="private" aria-pressed="${filter === 'private'}">${tr('企业资料', 'Company documents')}</button><button data-kb-filter="public" aria-pressed="${filter === 'public'}">${tr('公共政策', 'Trade policies')}</button></div><input id="kb-filter" aria-label="${tr('筛选资料', 'Filter documents')}" placeholder="${tr('按文件名或订单查找', 'Find a document or order')}" value="${escape(query)}"></div><div id="kb-library-live">${rows()}</div></section>`;
  }
  function composer() {
    const docs = documents.filter(d => d.current_version && (!order() || d.tenant === 'public' || !d.metadata.order_id || d.metadata.order_id === order()));
    return `<div class="kb-context" data-user-content><span>↳ ${tr('检索范围', 'Search in')}</span><select id="kb-chat-document" aria-label="${tr('助手检索范围', 'Assistant search scope')}"><option value="">${order() ? tr('本订单 + 企业共用 + 公共政策', 'This order + shared files + policies') : tr('全部可用资料', 'All available documents')}</option>${docs.map(d => `<option value="${d.id}" ${selectedDocument() === d.id ? 'selected' : ''}>${escape(title(d))}</option>`).join('')}</select></div>`;
  }
  function answer(turn) {
    const r = turn.rag;
    if (r.status === 'pending') return `<div class="kb-answer" data-user-content role="status">${tr('正在检索相关资料…', 'Searching relevant evidence…')}</div>`;
    if (r.status === 'error') return `<div class="kb-answer" data-user-content><p>${tr('这次未能完成检索：', 'The search could not complete: ')}${escape(r.error)}</p><button class="tf-link" data-kb-retry="${turn.id}">${tr('重新提问', 'Try again')}</button></div>`;
    return `<div class="kb-answer" data-user-content><span class="kb-answer-mode">${r.mode === 'model' ? escape(r.model) + ' · ' + tr('依据资料回答', 'Source-grounded answer') : tr('检索摘录 · 未连接生成模型', 'Retrieved excerpts · No generation model connected')}</span>${r.paragraphs.map(p => `<p class="kb-answer-text">${escape(p.text)} ${p.sources.map(id => `<button class="kb-citation" data-kb-cite="${turn.id}:${id}" aria-label="${tr('查看引用', 'View source')} ${id}">[${id}]</button>`).join(' ')}</p>`).join('')}${r.follow_up ? `<p class="tf-small">${escape(r.follow_up)}</p>` : ''}${r.sources.length ? `<details class="kb-sources" open><summary>${tr('引用来源', 'Sources')} · ${r.sources.length}</summary>${r.sources.map(s => `<button class="kb-source" data-kb-cite="${turn.id}:${s.id}"><span>[${s.id}] ${escape(s.title)}</span><small>v${s.version} · ${escape(s.locator)}${s.review_due ? ' · ' + tr('待复核', 'Review due') : ''}</small></button>`).join('')}</details>` : ''}</div>`;
  }
  async function refresh() {
    try {
      [documents, status] = await Promise.all([knowledgeAPI('/documents'), knowledgeAPI('/health')]);
      error = '';
    } catch (e) { error = tr('知识库未连接：', 'Library disconnected: ') + e.message; }
    const live = root.querySelector('#kb-library-live');
    if (live) live.innerHTML = rows();
    // Only replace the scope control; never replace a user's unsent question.
    const context = root.querySelector('.kb-context');
    if (context) context.outerHTML = composer();
  }
  async function upload(file, orderId = '') {
    const data = new FormData(); data.append('file', file); data.append('order_id', orderId);
    const record = await knowledgeAPI('/uploads', { method: 'POST', body: data });
    notice = tr(`已上传 ${file.name}，正在后台解析。`, `${file.name} uploaded. Indexing in the background.`);
    filter = 'private'; await refresh(); return record;
  }
  async function open(id, version, citation) {
    const doc = await knowledgeAPI('/documents/' + id + (version ? '/versions/' + version : ''));
    let dialog = document.getElementById('kb-viewer');
    if (!dialog) { dialog = document.createElement('dialog'); dialog.id = 'kb-viewer'; dialog.className = 'kb-viewer'; document.body.append(dialog); }
    dialog.innerHTML = `<div class="kb-heading"><h2>${escape(title(doc))}</h2><button id="kb-close" aria-label="${tr('关闭来源', 'Close source')}">×</button></div><p>${tr('引用版本', 'Source version')} v${doc.selected_version} · ${tr('当前版本', 'Current version')} v${doc.current_version}</p>${citation ? `<blockquote><strong>${escape(citation.locator)}</strong><br>${escape(citation.excerpt)}</blockquote>` : ''}<div class="kb-source-body">${doc.content.map(p => `<section><small>${escape(p.locator)}</small><p>${escape(p.text)}</p></section>`).join('') || tr('文件仍在处理中。', 'Document processing is in progress.')}</div><div class="kb-source-links"><a href="/api/documents/${id}/versions/${version || doc.latest_version}/original">${tr('下载该版本原件', 'Download this version')}</a>${safeURL(citation?.source_url || doc.metadata.source_url) ? `<a href="${safeURL(citation?.source_url || doc.metadata.source_url)}" target="_blank" rel="noopener">${tr('查看官方来源', 'Official source')} ↗</a>` : ''}</div>`;
    dialog.querySelector('#kb-close').onclick = () => dialog.close(); dialog.showModal();
  }
  root.addEventListener('input', e => { if (e.target.id === 'kb-filter') { query = e.target.value; root.querySelector('#kb-library-live').innerHTML = rows(); } });
  root.addEventListener('click', async e => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.kbFilter) { filter = b.dataset.kbFilter; rerender(); }
    try {
      if (b.dataset.kbOpen) await open(b.dataset.kbOpen);
      if (b.dataset.kbAsk) selectDocument(documents.find(d => d.id === b.dataset.kbAsk), true);
    } catch (e) { error = e.message; rerender(); }
  });
  root.addEventListener('change', e => { if (e.target.id === 'kb-chat-document') selectDocument(documents.find(d => d.id === e.target.value) || null, false); });
  root.addEventListener('submit', async e => {
    if (e.target.id !== 'kb-upload-form') return;
    e.preventDefault(); if (uploading) return;
    const file = root.querySelector('#kb-file').files[0], orderId = root.querySelector('#kb-order').value;
    uploading = true; e.target.querySelector('button').disabled = true;
    try { await upload(file, orderId); e.target.reset(); } catch (e) { error = e.message; }
    uploading = false; rerender();
  });
  return { view, composer, answer, upload, refresh, open };
}

export async function askKnowledge({ question, language, document_id, order_id, history }) {
  return knowledgeAPI('/assistant/chat', post({ question, language, document_id: document_id || null, order_id: order_id || null, history }));
}
