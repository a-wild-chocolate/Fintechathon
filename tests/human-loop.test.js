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
