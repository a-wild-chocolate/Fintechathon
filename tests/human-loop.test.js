import test from 'node:test';
import assert from 'node:assert/strict';
import {renderHumanQuestions,collectHumanAnswers,humanReplySummary} from '../src/human-loop.js';
const turn = () => ({id:'t',rag:{questions:[{id:'q',question:'Which payment?',options:['Buyer receipt','Supplier payment']}]}});
test('questions have no default selection and offer comments and skipping in both languages',()=>{
  const t=turn();
  assert.doesNotMatch(renderHumanQuestions(t,'en'),/checked/);
  assert.match(renderHumanQuestions(t,'en'),/Skip this question/);
  assert.match(renderHumanQuestions(t,'zh'),/暂不回答/);
  assert.throws(()=>collectHumanAnswers(t));
  t.humanDraft={q:{comment:'This is the supplier payment.'}};
  assert.equal(collectHumanAnswers(t)[0].option_index,null);
  assert.equal(collectHumanAnswers(t)[0].action,'answer');
});
test('skip overrides a previous option while preserving a note',()=>{
  const t=turn();t.humanDraft={q:{choice:'0',comment:'Please check later'}};
  const answers=collectHumanAnswers(t,true);
  assert.equal(answers[0].action,'skip');assert.equal(answers[0].option_index,null);
  assert.equal(answers[0].comment,'Please check later');
  const saved=JSON.parse(JSON.stringify(t));assert.match(renderHumanQuestions(saved,'en'),/checked/);
});
test('submitted answers replace the form and escape document-like text',()=>{
  const t=turn();t.rag.questions[0].question='<script>bad</script>';
  assert.doesNotMatch(renderHumanQuestions(t,'en'),/<script>/);
  t.rag.human_response={answers:[{question:'Which payment?',action:'answer',selected_option:'Supplier payment',comment:'10 days'}]};
  assert.doesNotMatch(renderHumanQuestions(t,'en'),/<form/);
  assert.match(humanReplySummary(t.rag.human_response,'en'),/Supplier payment · 10 days/);
});

import { turnProgress, renderAgentProgress } from '../src/agent-progress.js';
test('submitted or skipped clarification is answered, not waiting or falsely completed',()=>{
 const r={task_status:'needs_information',trace:[],human_response:{run_id:'next',status:'running'}};
 const progress=turnProgress(r);
 assert.equal(progress.status,'answered');
 assert.equal(r.task_status,'needs_information');
 const html=renderAgentProgress(progress,'en');
 assert.match(html,/Response received/);
 assert.doesNotMatch(html,/Waiting for information|Analysis complete|indicator running/);
 assert.match(renderAgentProgress(progress,'zh'),/回答已收到/);
 assert.equal(turnProgress({task_status:'needs_information'}).status,'needs_information');
});

import { createKnowledgeUI } from '../src/knowledge.js';
test('the answer renderer uses the saved response rather than the historical waiting status', () => {
 const ui=createKnowledgeUI({root:{addEventListener(){}},language:()=> 'en',order:()=> 'TF-26104'});
 const t=turn();
 Object.assign(t.rag,{status:'done',mode:'multi_agent',task_status:'needs_information',trace:[],paragraphs:[],sources:[],human_response:{run_id:'child'}});
 const html=ui.answer(t);
 assert.match(html,/Response received/);
 assert.doesNotMatch(html,/Waiting for information|data-human-form/);
 delete t.rag.human_response;
 assert.match(ui.answer(t),/Waiting for information/);
 assert.match(ui.answer(t),/data-human-form/);
});
