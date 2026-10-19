/** Conversation presentation; model execution stays in the background task layer. */
const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
export const shouldSend = event => event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229;
export const nearConversationEnd = (height, scroll, viewport) => height - scroll - viewport < 180;
const atEnd = panel => nearConversationEnd(panel.scrollHeight, panel.scrollTop, panel.clientHeight);
const positions = new Map();

export function rememberChatScroll(root) {
  const panel = root.querySelector('.tx-messages');
  if (panel?.dataset.scrollKey) positions.set(panel.dataset.scrollKey, {top: panel.scrollTop, follow: atEnd(panel)});
}

const followConversation = panel => panel.scrollTo({top: panel.scrollHeight, behavior: 'instant'});
const reveal = element => {
  if (!reducedMotion()) element.animate([{ opacity: 0, transform: 'translateY(5px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 240, easing: 'ease-out' });
};
const seen = new Set();
let initialized = false;

export function setupChat(root, language, key) {
  const chat = root.querySelector('.tx-chat');
  if (!chat) return;
  const en = language === 'en';
  const empty = Boolean(chat.querySelector('.tx-chat-empty'));
  chat.classList.toggle('is-empty', empty);
  const messages = chat.querySelector('.tx-messages');
  messages.removeAttribute('aria-live');
  const mounted = Boolean(messages.dataset.scrollKey);
  if (!mounted) messages.dataset.scrollKey = key || 'conversation';
  messages.setAttribute('role', 'region');
  messages.setAttribute('aria-label', en ? 'Conversation history' : '对话记录');
  messages.tabIndex = 0;
  messages.onscroll = () => rememberChatScroll(root);
  const composer = chat.querySelector('.tx-composer');
  const hints = chat.querySelector('.tx-chat-hints');
  if (hints && !hints.hidden) composer.before(hints);
  const input = chat.querySelector('#tf-ai-question');
  const submit = chat.querySelector('[data-action="ai-submit"]');
  const busy = Boolean(chat.querySelector('[data-chat-status="pending"]'));
  if (input && submit) {
    input.rows = 1;
    input.placeholder = en ? 'Ask CashWeave about your business…' : '和 CashWeave 聊聊订单、回款与资金安排…';
    submit.setAttribute('aria-label', en ? 'Send message' : '发送消息');
    submit.title = busy ? (en ? 'Analysis is running. You can prepare your next message.' : '分析进行中，可以先写下一个问题') : (en ? 'Send message' : '发送消息');
    submit.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 19V5m-6 6 6-6 6 6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    const resize = () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 180) + 'px';
      submit.disabled = busy || !input.value.trim();
    };
    input.oninput = resize;
    input.onkeydown = event => {
      if (shouldSend(event)) { event.preventDefault(); if (!submit.disabled) submit.click(); }
    };
    chat.querySelector('.tx-send-row .tf-note').textContent = en ? 'Enter to send · Shift + Enter for a new line' : 'Enter 发送 · Shift + Enter 换行';
    resize();
  }
  let latest;
  for (const reply of chat.querySelectorAll('[data-reply-id]')) {
    if (!seen.has(reply.dataset.replyId)) {
      if (initialized) { reveal(reply.previousElementSibling); reveal(reply); latest = reply; }
      seen.add(reply.dataset.replyId);
    }
  }
  initialized = true;
  if (!mounted || latest) {
    const position = positions.get(messages.dataset.scrollKey);
    requestAnimationFrame(() => {
      if (latest || !position || position.follow) followConversation(messages);
      else messages.scrollTop = position.top;
      rememberChatScroll(root);
    });
  }
}

export function replaceChatReply(root, turn, html, language) {
  const current = root.querySelector(`[data-reply-id="${turn.id}"]`);
  if (!current) return false;
  const panel = current.closest('.tx-messages');
  const follow = atEnd(panel);
  const top = panel.scrollTop;
  const template = document.createElement('template');
  template.innerHTML = html;
  const next = template.content.querySelector('.tx-chat-reply');
  current.replaceWith(next);
  reveal(next);
  setupChat(root, language);
  requestAnimationFrame(() => {
    if (follow) followConversation(panel);
    else panel.scrollTop = top;
    rememberChatScroll(root);
  });
  return true;
}
