export function restoreAgentTasks(turns) {
  for (const turn of turns) {
    if (turn.rag?.status !== 'pending') continue;
    if (!turn.rag.progress?.run_id) {
      turn.rag = {...turn.rag, status:'error', error:'No saved run ID. This request cannot reconnect automatically.'};
    }
  }
  return turns.filter(t => t.rag?.status === 'pending' && t.rag.progress?.run_id);
}

export function archiveConversation(turns, scope) {
  for (const turn of turns) if (turn.scope === scope) turn.archived = true;
}

export function retainAgentTasks(turns, limit = 12) {
  const recent = new Set(turns.slice(-limit));
  return turns.filter(t => recent.has(t) || t.rag?.status === 'pending' || t.unread || t.rag?.progress?.status === 'running');
}

export function rememberAgentSession(turn, sessionId, sessions) {
  if (!sessionId || turn.archived) return;
  const key = JSON.stringify([turn.orderId, turn.documentId]);
  if (!sessions[key] || sessions[key] === sessionId) sessions[key] = sessionId;
}
