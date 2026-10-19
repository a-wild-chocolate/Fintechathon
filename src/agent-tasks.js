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
  const selected = turns.filter(t => !t.archived || recent.has(t) || t.rag?.status === 'pending' || t.unread || t.rag?.progress?.status === 'running');
  return linkedConversation(turns, selected);
}

// Clarification replies remain part of the request that prompted them, including saved legacy turns.
export function linkedConversation(turns, selected) {
  const included = new Set(selected);
  const byRun = new Map(turns.map(turn => [turn.rag?.run_id || turn.rag?.progress?.run_id, turn]).filter(([id]) => id));
  const links = turns.map(parent => [parent, byRun.get(parent.rag?.human_response?.run_id)]).filter(([, child]) => child);
  let changed = true;
  while (changed) {
    changed = false;
    for (const [parent, child] of links) {
      if ((included.has(parent) || included.has(child)) && !(included.has(parent) && included.has(child))) {
        included.add(parent); included.add(child); changed = true;
      }
    }
  }
  return turns.filter(turn => included.has(turn));
}

export function rememberAgentSession(turn, sessionId, sessions) {
  if (!sessionId || turn.archived) return;
  const key = JSON.stringify([turn.orderId, turn.documentId]);
  if (!sessions[key] || sessions[key] === sessionId) sessions[key] = sessionId;
}
