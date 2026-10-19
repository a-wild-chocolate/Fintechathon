import test from 'node:test';
import assert from 'node:assert/strict';
import {restoreAgentTasks,archiveConversation,retainAgentTasks,rememberAgentSession} from '../src/agent-tasks.js';
test('reload keeps a running task reconnectable without posting again',()=>{
 const task={id:'a',scope:'buyer',rag:{status:'pending',progress:{run_id:'r',status:'running'}}};
 const saved=JSON.parse(JSON.stringify([task]));
 assert.equal(restoreAgentTasks(saved)[0].rag.progress.run_id,'r');
 assert.equal(saved[0].rag.status,'pending');
});
test('new chat and history trimming keep live and unread tasks',()=>{
 const task={id:'a',scope:'buyer',rag:{status:'pending',progress:{run_id:'r'}}};
 const turns=[task,...Array.from({length:20},(_,i)=>({id:i,scope:'company',rag:{status:'done'}}))];
 archiveConversation(turns,'buyer');
 assert.equal(task.archived,true);assert.equal(task.rag.status,'pending');
 assert.ok(retainAgentTasks(turns).includes(task));
 task.rag.status='done';task.unread=true;
 assert.ok(retainAgentTasks(turns).includes(task));
});
test('a legacy pending request without an ID is not silently resubmitted',()=>{
 const turns=[{rag:{status:'pending'}}];assert.deepEqual(restoreAgentTasks(turns),[]);
 assert.equal(turns[0].rag.status,'error');
});

test('old background completion does not replace the new conversation session',()=>{
 const turn={orderId:'TF-26104',documentId:'email',archived:true};
 const key=JSON.stringify([turn.orderId,turn.documentId]);
 const sessions={};
 rememberAgentSession(turn,'old-session',sessions);
 assert.equal(sessions[key],undefined);
 sessions[key]='new-session';turn.archived=false;
 rememberAgentSession(turn,'old-session',sessions);
 assert.equal(sessions[key],'new-session');
});

const clarification = (id, next, status = 'done') => ({id, rag: {
 status, run_id: id, task_status: 'needs_information', questions: [{id:'question'}],
 ...(next ? {human_response: {run_id: next}} : {}),
}});

test('answered clarification and its running continuation stay together after reload', () => {
 const earlier = {id:'older', rag:{status:'done'}};
 const parent = clarification('parent','child');
 const child = {id:'reply',rag:{status:'pending',progress:{run_id:'child'}}};
 const saved = JSON.parse(JSON.stringify([earlier,parent,child]));
 assert.deepEqual(retainAgentTasks(saved, 1).map(t=>t.id), ['older','parent','reply']);
});

test('multiple clarification rounds keep their original question visible through completion or failure', () => {
 const a=clarification('a','b'), b=clarification('b','c');
 for(const status of ['completed','failed','needs_information']) {
  const c={id:'c',rag:{status:'done',run_id:'c',task_status:status}};
  const turns=[a,b,c];
  assert.deepEqual(retainAgentTasks(turns,1),turns);
 }
 const fresh={id:'new',rag:{status:'done',task_status:'completed'}};
 const turns = [a,b,{id:'c',rag:{run_id:'c',status:'done'}},fresh];
 assert.deepEqual(retainAgentTasks(turns, 1), turns);
});

test('long active conversations retain every message while old archived replies can expire', () => {
 const old = {id:'archived',archived:true,rag:{status:'done'}};
 const active = Array.from({length:30}, (_, id) => ({id,rag:{status:'done'}}));
 assert.deepEqual(retainAgentTasks([old,...active]), active);
});

test('opening a task restores its clarification thread and reads only that result', async () => {
  const {openAgentTask} = await import('../src/agent-tasks.js');
  const turns = [
    {id:'question', archived:true, unread:false, rag:{run_id:'r1', human_response:{run_id:'r2'}}},
    {id:'answer', archived:true, unread:true, rag:{run_id:'r2'}},
    {id:'other', archived:true, unread:true, rag:{run_id:'r3'}},
  ];
  assert.equal(openAgentTask(turns,'answer'), turns[1]);
  assert.equal(turns[0].archived, false);
  assert.equal(turns[1].archived, false);
  assert.equal(turns[1].unread, false);
  assert.equal(turns[2].unread, true);
  assert.equal(turns[2].archived, true);
});
