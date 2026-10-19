"""Structured clarification contracts, independent of the model provider."""
import json
from typing import Literal
from uuid import uuid4
from pydantic import BaseModel, Field


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    context: str = Field(default='', max_length=400)
    options: list[str] = Field(min_length=2, max_length=4)


class HumanAnswer(BaseModel):
    question_id: str
    action: Literal['answer', 'skip']
    option_index: int | None = Field(default=None, ge=0, le=3)
    comment: str = Field(default='', max_length=1000)


def question_cards(output, proposal, language, specialist_results, human_answers=()):
    questions = output.get('questions', [])
    if not questions:
        questions = [q for result in specialist_results.values() for q in result.get('questions', [])][:3]
    en = language == 'en'
    skipped_fields = {a.get('field') for a in human_answers if a['action'] == 'skip'}
    skipped_questions = {a['question'] for a in human_answers if a['action'] == 'skip'}
    if not questions and proposal and proposal.get('missing_fields'):
        fields = {
            'amount_usd': ('客户本次计划支付多少美元？', 'How much USD does the buyer plan to pay this time?',
                           ['金额已知，我在留言中填写', '客户尚未明确金额'],
                           ['I know the amount; I will enter it below', 'The buyer has not specified an amount']),
            'receipt_date': ('这笔款项预计哪天可用？', 'When is this payment expected to be available?',
                             ['日期已知，我在留言中填写', '客户尚未明确日期'],
                             ['I know the date; I will enter it below', 'The buyer has not specified a date']),
        }
        questions = [{'question': fields[f][int(en)], 'options': fields[f][3 if en else 2],
                      'field': f, 'context': 'Leave this unknown if it has not been agreed.' if en else '尚未约定的信息可以保留未知。'}
                     for f in proposal['missing_fields'] if f in fields and f not in skipped_fields]
    if not questions and output.get('follow_up') and not human_answers:
        questions = [{'question': output['follow_up'][:300], 'options':
                      ['I can add details below', 'This is not known yet'] if en else ['我可以在下方补充', '目前还不清楚']}]
    return [dict(Question.model_validate(q).model_dump(), id=str(uuid4()), field=q.get('field'))
            for q in questions[:3] if q['question'] not in skipped_questions]


def resolve_answers(questions, answers):
    if len(answers) != len(questions) or {a.question_id for a in answers} != {q['id'] for q in questions}:
        raise ValueError('Answer or skip each question once.')
    by_id = {q['id']: q for q in questions}
    result = []
    for answer in answers:
        q = by_id[answer.question_id]
        if answer.action == 'skip' and answer.option_index is not None:
            raise ValueError('A skipped question cannot also select an option.')
        if answer.option_index is not None and answer.option_index >= len(q['options']):
            raise ValueError('Choose an option from this question.')
        comment = answer.comment.strip()
        if answer.action == 'answer' and answer.option_index is None and not comment:
            raise ValueError('Choose an option, add a comment, or skip the question.')
        result.append({'question_id': q['id'], 'question': q['question'], 'action': answer.action,
                       'selected_option': q['options'][answer.option_index] if answer.option_index is not None else None,
                       'comment': comment, 'field': q.get('field')})
    return result


def reply_text(answers):
    return 'User clarification responses:\n' + json.dumps(answers, ensure_ascii=False)
