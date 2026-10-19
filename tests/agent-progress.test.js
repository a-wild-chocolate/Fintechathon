import test from 'node:test';
import assert from 'node:assert/strict';
import {progressState,renderAgentProgress} from '../src/agent-progress.js';
const trace = [
 {event:'agent_started',agent:'coordinator'},
 {event:'model_started',agent:'coordinator'}, {event:'model_call',agent:'coordinator'},
 {event:'tool_started',agent:'coordinator',tool:'wf_dispatch'},
 {event:'agent_started',agent:'cash_flow'},
 {event:'model_started',agent:'cash_flow'}, {event:'model_call',agent:'cash_flow'},
 {event:'tool_started',agent:'cash_flow',tool:'wf_cash'},
];
test('delegation shows the active child and the actual pending operation',()=>{
 const state=progressState(trace);
 assert.equal(state.active.agent,'cash_flow');assert.equal(state.active.tool,'wf_cash');
 assert.equal(state.steps[0].status,'done');assert.equal(state.agents.coordinator,'working');
 const en=renderAgentProgress({trace},'en');const zh=renderAgentProgress({trace},'zh');
 assert.match(en,/Calculating cash flow and shortfalls/);assert.match(zh,/计算现金流与资金缺口/);
 assert.doesNotMatch(en,/Reconciliation/);
});
test('failure stops active indicators rather than claiming completion',()=>{
 const state=progressState(trace,'failed');assert.equal(state.active,undefined);
 assert.equal(state.steps.at(-1).status,'stopped');
 assert.match(renderAgentProgress({trace,status:'failed'},'en',false),/Analysis incomplete/);
});
test('tool errors and successful completion stay distinguishable',()=>{
 const events=[...trace,{event:'tool_error',agent:'cash_flow',tool:'wf_cash'},{event:'agent_finished',agent:'cash_flow'}];
 assert.equal(progressState(events).steps.at(-1).status,'error');
 assert.equal(progressState(events).agents.cash_flow,'done');
 assert.match(renderAgentProgress({trace:events,status:'needs_information'},'en',false),/Waiting for information/);
});

test('live transport starts once and polls the same run until the result arrives',async()=>{
 const {askKnowledge,watchAgentRun}=await import('../src/knowledge.js');
 const original=globalThis.fetch, requests=[],updates=[];
 const result={mode:'multi_agent',task_status:'completed',paragraphs:[],sources:[]};
 let reads=0;
 globalThis.fetch=async (url,options={})=>{
   requests.push([url,options.method || 'GET']);
   const body=options.method==='POST' ? {run_id:'test-run',session_id:'s',status:'running'} : ++reads===1 ? {run_id:'test-run',status:'running',trace} : {run_id:'test-run',status:'completed',result};
   return new Response(JSON.stringify(body),{status:options.method==='POST'?202:200});
 };
 try {
   assert.deepEqual(await askKnowledge({question:'test',live:true,onProgress:p=>updates.push(p)}),result);
   assert.equal(requests.filter(r=>r[1]==='POST').length,1);
   assert.equal(updates[1].trace.at(-1).tool,'wf_cash');
   assert.deepEqual(await watchAgentRun('test-run'),result);
   assert.equal(requests.filter(r=>r[1]==='POST').length,1);
 } finally {globalThis.fetch=original;}
});

test('live progress shows the current operation and keeps the full trace in a disclosure',()=>{
 const html=renderAgentProgress({trace},'en');
 assert.match(html,/kb-progress-indicator running/);
 assert.match(html,/<details class="kb-progress" /);
 assert.doesNotMatch(html,/<details[^>]+ open/);
 assert.match(renderAgentProgress({trace},'en',true), /<details[^>]+ open/);
 assert.doesNotMatch(html,/kb-agent-lanes|kb-live-label|kb-progress-orb/);
 const visible=html.slice(0,html.indexOf('</summary>'));
 assert.equal((visible.match(/Calculating cash flow and shortfalls/g)||[]).length,1);
 assert.doesNotMatch(visible,/Understanding the request/);
});

test('continuation activity distinguishes reused specialists from model execution', () => {
  const run = {status:'running',trace:[
    {event:'resume_planned',agent:'coordinator',rerun_roles:['decision'],reused_roles:['cash_flow']},
    {event:'agent_reused',agent:'cash_flow',from_run_id:'previous'},
    {event:'model_started',agent:'decision'},
  ]};
  const state = progressState(run.trace, run.status);
  assert.equal(state.steps.find(step => step.agent === 'cash_flow').status, 'reused');
  assert.equal(state.active.agent, 'decision');
  const html=renderAgentProgress(run,'en',true);
  assert.match(html,/Reusing the completed result; no model call/);
  assert.match(html,/Reused/);
});

test('saved calculations remain visible without implying a specialist model ran', () => {
  const trace=[{event:'workflow_reused',agent:'cash_flow',tool:'wf_cash'}];
  assert.equal(progressState(trace).active, undefined);
  assert.match(renderAgentProgress({trace,status:'completed'},'en',true), /Reusing the saved calculation; no model call/);
  assert.match(renderAgentProgress({trace,status:'completed'},'zh',true), /复用已有计算/);
});


test('a confirmed proposal no longer shows a waiting indicator', async () => {
  const {turnProgress} = await import('../src/agent-progress.js');
  const progress = turnProgress({trace:[], task_status:'needs_approval', proposal:{status:'confirmed'}});
  assert.equal(progress.status,'confirmed');
  assert.match(renderAgentProgress(progress,'en'),/Confirmed and updated/);
  assert.doesNotMatch(renderAgentProgress(progress,'en'),/Waiting for confirmation/);
});
