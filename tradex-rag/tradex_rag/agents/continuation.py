"""Dependency-aware reuse of specialist results after a clarification."""
from copy import deepcopy
from typing import Literal
from pydantic import BaseModel, Field

SPECIALISTS = ('reconciliation', 'cash_flow', 'decision')
DOWNSTREAM = {'reconciliation': {'cash_flow', 'decision'}, 'cash_flow': {'decision'}, 'decision': set()}


class CashScenario(BaseModel):
    receipt_delay_days: int = 0
    supplier_extension_days: int = 0
    use_proposal: bool = False


class ResumePlan(BaseModel):
    rerun_roles: list[Literal['reconciliation', 'cash_flow', 'decision']] = Field(max_length=3)
    decision_task: Literal['general', 'draft'] = Field(description='Use draft when the user chose correspondence to prepare. That task needs only the final reply and full draft, not further research.')
    cash_scenarios: list[CashScenario] = Field(default_factory=list, description='New cash scenarios explicitly requested by the reply. Leave empty for an action preference or unchanged dates and amounts.')
    reason: str = Field(min_length=1, max_length=500)


class Continuation:
    def __init__(self, turn, parent):
        self.turn = turn
        self.parent = parent
        self.results = parent['result'].get('specialist_results', {})
        self.facts = parent['result'].get('workflow_facts', {})
        self.dependencies = parent['result'].get('specialist_sources', {})
        self.planned = False
        self.rerun = set()
        self.required = set()
        self.scenarios = []
        self.decision_task = 'general'
        store, tenant = turn.runtime.store, turn.runtime.tenant
        self.workspace = store.workspace(tenant)
        self.proposal = store.proposal(tenant, parent['session_id'])
        if self.workspace != parent['result'].get('workspace'):
            self.required.update(role for role in ('cash_flow', 'decision') if role in self.results or role in self.facts)
        self.changed_sources = []
        for role, result in self.results.items():
            references = {ref for paragraph in result['paragraphs'] for ref in paragraph['sources']}
            dependencies = {source['document_id']: source['version'] for source in parent['result'].get('sources', [])
                            if source['id'] in references and source.get('kind') != 'web'}
            dependencies.update(self.dependencies.get(role, {}))
            for document_id, version in dependencies.items():
                doc = turn.runtime.library.document(document_id, tenant)
                if doc['current_version'] != version:
                    self.changed_sources.append(document_id)
                    self.required.add(role)
        if any(answer.get('field') in {'amount', 'amount_usd', 'receipt_date'} and answer['action'] == 'answer'
               for answer in turn.request.get('human_answers', [])):
            self.required.add('reconciliation')
        self.cash_facts = []
        if self.workspace and not self.required.intersection({'cash_flow', 'reconciliation'}):
            for facts in self.facts.values():
                for fact in facts:
                    if fact['tool'] != 'wf_cash' or fact['result'].get('state_version') != (self.workspace or {}).get('version'):
                        continue
                    if fact['arguments'].get('use_proposal') and self.proposal != parent['result'].get('proposal'):
                        continue
                    normalized = dict(deepcopy(fact), arguments=CashScenario.model_validate(fact['arguments']).model_dump())
                    if normalized not in self.cash_facts:
                        self.cash_facts.append(normalized)

    def context(self):
        return {'original_question': self.parent['request'].get('original_question', self.parent['request']['question']),
                'prior_specialist_results': {
                    role: ({key: value for key, value in result.items() if key != 'paragraphs'}
                           if role in {'cash_flow', 'decision'} and self.cash_facts else result)
                    for role, result in self.results.items()},
                'prior_workflow_facts': {role: [f for f in facts if f['tool'] not in {'wf_status', 'wf_cash'}]
                                        for role, facts in self.facts.items()},
                'current_workspace': self.workspace, 'current_proposal': self.proposal,
                'changed_source_ids': self.changed_sources, 'required_roles': sorted(self.required),
                'cash_scenarios': self.scenarios,
                'available_cash_calculations': self.cash_facts}

    def plan(self, rerun_roles, reason, cash_scenarios=(), decision_task='general'):
        if self.planned:
            return {'error': 'The continuation plan is already set.'}
        rerun = set(rerun_roles) | self.required
        self.decision_task = decision_task
        if decision_task == 'draft':
            rerun.add('decision')
        scenarios = [CashScenario.model_validate(s).model_dump() for s in cash_scenarios]
        available = [CashScenario.model_validate(f['arguments']).model_dump() for f in self.cash_facts]
        missing = [scenario for scenario in scenarios if scenario not in available]
        self.scenarios = missing
        if missing:
            rerun.add('cash_flow')
        elif available and 'cash_flow' not in self.required and 'reconciliation' not in rerun:
            rerun.discard('cash_flow')
        for role in tuple(rerun):
            rerun.update(DOWNSTREAM[role] & self.results.keys())
        self.rerun = rerun
        self.planned = True
        reused = {role: deepcopy(result) for role, result in self.results.items()
                  if role not in rerun and result['status'] == 'completed'}
        self.turn.outputs.update(reused)
        self.turn.facts.update({role: deepcopy(self.facts.get(role, [])) for role in reused})
        self.turn.dependencies.update({role: deepcopy(self.dependencies.get(role, {})) for role in reused})
        if self.cash_facts and not rerun.intersection({'cash_flow', 'reconciliation'}):
            self.turn.facts['cash_flow'] = deepcopy(self.cash_facts)
            self.turn.record({'event': 'workflow_reused', 'agent': 'cash_flow', 'tool': 'wf_cash',
                              'from_run_id': self.parent['id'], 'count': len(self.cash_facts)})
        self.turn.record({'event': 'resume_planned', 'agent': 'coordinator',
                          'rerun_roles': sorted(rerun), 'reused_roles': sorted(reused), 'reason': reason})
        for role in reused:
            self.turn.record({'event': 'agent_reused', 'agent': role, 'from_run_id': self.parent['id']})
        return {'rerun_roles': sorted(rerun), 'reused_results': reused, 'cash_scenarios': missing,
                'reused_cash_calculations': self.turn.facts.get('cash_flow', []),
                'instruction': 'Call only the listed roles, in dependency order when needed, then synthesize.'}
