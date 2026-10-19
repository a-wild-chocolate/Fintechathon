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
