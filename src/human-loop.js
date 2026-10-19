const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export function renderHumanQuestions(turn, language) {
  const r = turn.rag, questions = r.questions || [];
  if (!questions.length) return '';
  const en = language === 'en', tr = (zh, english) => en ? english : zh;
  if (r.human_response) return `<p class="kb-human-submitted">✓ ${tr('回答已保存，后续分析见下方。', 'Responses saved. Follow-up analysis is below.')}</p>`;
  return `<form class="kb-human" data-human-form="${esc(turn.id)}" data-user-content>
    <header><strong>${tr('需要你补充一点信息', 'A quick clarification')}</strong><p>${tr('选择、留言或暂不回答，由你决定。', 'Choose an option, leave a note, or skip.')}</p></header>
    ${questions.map(q => {
      const draft = turn.humanDraft?.[q.id] || {};
      return `<fieldset><legend>${esc(q.question)}</legend>${q.context ? `<p>${esc(q.context)}</p>` : ''}
        <div class="kb-human-options">${[...q.options, tr('暂不回答', 'Skip this question')].map((option, i) => {
          const value = i === q.options.length ? 'skip' : String(i);
          return `<label><input type="radio" name="human-${esc(turn.id)}-${esc(q.id)}" data-human-question="${esc(q.id)}" value="${value}" ${draft.choice === value ? 'checked' : ''}><span>${esc(option)}</span></label>`;
        }).join('')}</div>
        <textarea rows="2" maxlength="1000" data-human-comment="${esc(q.id)}" aria-label="${tr('留言：', 'Comment: ')}${esc(q.question)}" placeholder="${tr('也可以直接留言，例如具体金额、日期或你的判断…', 'Or leave a note: an amount, date, or your interpretation…')}">${esc(draft.comment || '')}</textarea></fieldset>`;
    }).join('')}
    <p class="kb-human-error" role="status">${esc(turn.humanError || '')}</p>
    <div class="kb-human-actions"><button class="tf-button primary" type="submit">${tr('按回答继续', 'Continue with my answers')}</button><button type="button" class="tf-link" data-human-skip="${esc(turn.id)}">${tr('全部跳过，继续已有分析', 'Skip all and continue')}</button></div>
  </form>`;
}

export function collectHumanAnswers(turn, skipAll = false) {
  return turn.rag.questions.map(q => {
    const draft = turn.humanDraft?.[q.id] || {};
    const skip = skipAll || draft.choice === 'skip';
    const comment = (draft.comment || '').trim();
    const option = draft.choice !== undefined && draft.choice !== 'skip' ? Number(draft.choice) : null;
    if (!skip && option === null && !comment) throw Error('incomplete');
    return {question_id:q.id, action:skip ? 'skip' : 'answer', option_index:skip ? null : option, comment};
  });
}

export function humanReplySummary(response, language) {
  const en = language === 'en';
  return response.answers.map(a => `${a.question}\n${a.action === 'skip' ? (en ? 'Skipped' : '暂不回答') : a.selected_option || ''}${a.comment ? `${a.selected_option || a.action === 'skip' ? ' · ' : ''}${a.comment}` : ''}`).join('\n\n');
}
