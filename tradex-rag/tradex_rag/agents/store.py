import json
import time
from uuid import uuid4
from ..db import Database
from ..service import Conflict, NotFound
from .human import resolve_answers, reply_text

SCHEMA = '''
CREATE TABLE IF NOT EXISTS agent_sessions(id TEXT PRIMARY KEY, tenant TEXT, scope TEXT, turns TEXT);
CREATE TABLE IF NOT EXISTS agent_runs(id TEXT PRIMARY KEY, session_id TEXT, tenant TEXT, request TEXT,
 status TEXT, trace TEXT, sources TEXT, result TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS agent_workspaces(tenant TEXT PRIMARY KEY, version INTEGER, snapshot TEXT);
CREATE TABLE IF NOT EXISTS agent_proposals(id TEXT PRIMARY KEY, tenant TEXT, session_id TEXT, run_id TEXT,
 base_version INTEGER, status TEXT, payload TEXT, result TEXT);
CREATE TABLE IF NOT EXISTS agent_artifacts(id TEXT PRIMARY KEY, tenant TEXT, run_id TEXT, kind TEXT, text TEXT);
'''

class AgentStore:
    def __init__(self, path):
        self.db = Database(path)
        with self.db.connect() as db: db.executescript(SCHEMA)

    def start(self, tenant, request):
        with self.db.connect(write=True) as db:
            return self._start(db, tenant, request)

    def _start(self, db, tenant, request):
        session = request.get('session_id') or str(uuid4())
        scope = json.dumps([request.get('order_id'), request.get('document_id')])
        row = db.execute('SELECT * FROM agent_sessions WHERE id=? AND tenant=?', (session, tenant)).fetchone()
        if row and row['scope'] != scope: raise Conflict('Start a new conversation when the selected order or document changes.')
        if request.get('session_id') and not row: raise NotFound('Conversation not found')
        if row:
            active = db.execute("SELECT id FROM agent_runs WHERE session_id=? AND status='running'", (session,)).fetchone()
            if active: raise Conflict('This conversation already has an active turn.')
            history = json.loads(row['turns'])
        else:
            history = []
            db.execute('INSERT INTO agent_sessions VALUES(?,?,?,?)', (session, tenant, scope, '[]'))
        run = str(uuid4())
        db.execute('INSERT INTO agent_runs VALUES(?,?,?,?,?,?,?,?,?)',
                   (run, session, tenant, json.dumps(request), 'running', '[]', '[]', None, time.time()))
        return run, session, history

    def respond(self, run_id, tenant, answers, language):
        with self.db.connect(write=True) as db:
            row = db.execute('SELECT * FROM agent_runs WHERE id=? AND tenant=?', (run_id, tenant)).fetchone()
            if not row: raise NotFound('Agent run not found')
            result = json.loads(row['result']) if row['result'] else {}
            if row['status'] != 'needs_information' or not result.get('questions'):
                raise Conflict('This run is not waiting for clarification.')
            resolved = resolve_answers(result['questions'], answers)
            if result.get('human_response'):
                if result['human_response']['answers'] != resolved:
                    raise Conflict('These questions have already been answered.')
                return result['human_response'], None
            latest = db.execute('SELECT id FROM agent_runs WHERE session_id=? ORDER BY rowid DESC LIMIT 1', (row['session_id'],)).fetchone()
            if latest['id'] != run_id:
                raise Conflict('Continue the latest conversation turn instead of answering an earlier question.')
            request = json.loads(row['request'])
            request.update(question=reply_text(resolved), session_id=row['session_id'], language=language,
                           human_answers=resolved, reply_to_run_id=run_id)
            next_run, session, history = self._start(db, tenant, request)
            response = {'run_id': next_run, 'session_id': session, 'status': 'running', 'answers': resolved}
            result['human_response'] = response
            db.execute('UPDATE agent_runs SET result=? WHERE id=?', (json.dumps(result, ensure_ascii=False), run_id))
        return response, (next_run, session, request, history)

    def run(self, run_id, tenant):
        with self.db.connect() as db:
            row = db.execute('SELECT * FROM agent_runs WHERE id=? AND tenant=?', (run_id, tenant)).fetchone()
        if not row: raise NotFound('Agent run not found')
        r = dict(row)
        for key in ('request', 'trace', 'sources', 'result'): r[key] = json.loads(r[key]) if r[key] else None
        return r

    def append(self, run_id, tenant, entry):
        with self.db.connect(write=True) as db:
            row = db.execute('SELECT trace FROM agent_runs WHERE id=? AND tenant=?', (run_id, tenant)).fetchone()
            trace = json.loads(row['trace']); trace.append(dict(entry, timestamp=time.time()))
            db.execute('UPDATE agent_runs SET trace=? WHERE id=?', (json.dumps(trace, ensure_ascii=False), run_id))

    def sources(self, run_id, tenant, new):
        with self.db.connect(write=True) as db:
            row = db.execute('SELECT sources FROM agent_runs WHERE id=? AND tenant=?', (run_id, tenant)).fetchone()
            sources = json.loads(row['sources'])
            for source in new:
                match = next((s for s in sources if (s['document_id'], s['version'], s['locator']) ==
                              (source['document_id'], source['version'], source['locator'])), None)
                if not match: sources.append(dict(source, id=len(sources)+1))
            db.execute('UPDATE agent_runs SET sources=? WHERE id=?', (json.dumps(sources, ensure_ascii=False), run_id))
        return sources

    def finish(self, run_id, tenant, result):
        with self.db.connect(write=True) as db:
            run = db.execute('SELECT * FROM agent_runs WHERE id=? AND tenant=?', (run_id, tenant)).fetchone()
            row = db.execute('SELECT turns FROM agent_sessions WHERE id=?', (run['session_id'],)).fetchone()
            history = json.loads(row['turns'])
            history.append({'question': json.loads(run['request'])['question'], 'answer': result})
            db.execute('UPDATE agent_runs SET status=?,result=? WHERE id=?',
                       (result['task_status'], json.dumps(result, ensure_ascii=False), run_id))
            db.execute('UPDATE agent_sessions SET turns=? WHERE id=?', (json.dumps(history[-4:], ensure_ascii=False), run['session_id']))

    def workspace(self, tenant):
        with self.db.connect() as db:
            row = db.execute('SELECT snapshot FROM agent_workspaces WHERE tenant=?', (tenant,)).fetchone()
        return json.loads(row['snapshot']) if row else None

    def import_workspace(self, tenant, snapshot):
        with self.db.connect(write=True) as db:
            row = db.execute('SELECT version FROM agent_workspaces WHERE tenant=?', (tenant,)).fetchone()
            if not row or snapshot['version'] > row['version']:
                db.execute('INSERT OR REPLACE INTO agent_workspaces VALUES(?,?,?)',
                           (tenant, snapshot['version'], json.dumps(snapshot)))
        return self.workspace(tenant)

    def proposal(self, tenant, session_id):
        with self.db.connect() as db:
            row = db.execute('SELECT * FROM agent_proposals WHERE tenant=? AND session_id=? ORDER BY rowid DESC LIMIT 1',
                             (tenant, session_id)).fetchone()
        if not row: return None
        return dict(id=row['id'], base_version=row['base_version'], status=row['status'], **json.loads(row['payload']))

    def save_proposal(self, run, payload, version):
        proposal_id = str(uuid4())
        status = 'needs_information' if payload['missing_fields'] else 'needs_approval'
        with self.db.connect(write=True) as db:
            db.execute("UPDATE agent_proposals SET status='superseded' WHERE tenant=? AND session_id=? AND status IN ('needs_information','needs_approval')",
                       (run['tenant'], run['session_id']))
            db.execute('INSERT INTO agent_proposals VALUES(?,?,?,?,?,?,?,?)',
                       (proposal_id, run['tenant'], run['session_id'], run['id'], version, status, json.dumps(payload), None))
        return self.proposal(run['tenant'], run['session_id'])

    def artifact(self, tenant, run_id, kind, text):
        artifact_id = str(uuid4())
        with self.db.connect(write=True) as db:
            db.execute('INSERT INTO agent_artifacts VALUES(?,?,?,?,?)', (artifact_id, tenant, run_id, kind, text))
        return {'artifact_id': artifact_id, 'kind': kind, 'text': text, 'status': 'draft'}
