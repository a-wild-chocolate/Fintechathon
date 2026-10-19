import json,re,threading,time
from datetime import date
from pathlib import Path
from uuid import uuid4
from .config import Settings
from .db import Database
from .embedding import provider
from .parsing import parse,chunk,lexical_tokens,SUPPORTED
from .vectors import VectorStore

class Conflict(ValueError):pass
class NotFound(ValueError):pass
class AccessDenied(ValueError):pass

RCEP_MARKETS={'CN','JP','SG','AU','VN','TH','KR','MY','ID','NZ','PH','BN','KH','LA','MM'}
class Library:
    def __init__(self,settings=None,embedding=None,clock=time.time):
        self.settings=settings or Settings();self.root=self.settings.data_dir
        self.root.mkdir(parents=True,exist_ok=True);(self.root/'files').mkdir(exist_ok=True)
        self.db=Database(self.root/'library.sqlite3');self.embedding=embedding or provider(self.settings)
        self.vectors=VectorStore(self.settings,self.embedding);self.clock=clock
        self.stop=threading.Event();self.wake=threading.Event();self.worker=None

    def _document(self,db,document_id,tenant,write=False):
        r=db.execute('SELECT * FROM documents WHERE id=? AND deleted=0',(document_id,)).fetchone()
        if not r or r['tenant'] not in {tenant,'public'}:raise NotFound('Document not found')
        if write and (r['tenant']=='public' or r['tenant']!=tenant):raise AccessDenied('Public policies are read-only through tenant tools')
        return dict(r)

    def _event(self,db,tenant,kind,doc,version,payload=None):
        db.execute('INSERT INTO events(tenant,kind,document_id,version,payload,created_at) VALUES(?,?,?,?,?,?)',
                   (tenant,kind,doc,version,json.dumps(payload or {},ensure_ascii=False),self.clock()))

    def _job(self,db,doc,version,operation='ingest'):
        job=str(uuid4());now=self.clock()
        db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',(job,doc,version,operation,'queued',None,now,now))
        return job

    def create(self,filename,content,title,tenant,metadata=None,source_key=None):
        suffix=Path(filename).suffix.lower()
        if suffix not in SUPPORTED:raise ValueError('Supported formats: '+', '.join(sorted(SUPPORTED)))
        metadata=dict(metadata or {});doc=str(uuid4())
        directory=self.root/'files'/doc/'v1';directory.mkdir(parents=True)
        path=directory/('source'+suffix);path.write_bytes(content)
        with self.db.connect(write=True) as db:
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?,1,0,0,?)',
                       (doc,tenant,title,source_key,json.dumps(metadata,ensure_ascii=False),self.clock()))
            db.execute('INSERT INTO versions VALUES(?,?,?,?,?,?)',(doc,1,Path(filename).name,str(path),'queued',self.clock()))
            job=self._job(db,doc,1);self._event(db,tenant,'document.uploaded',doc,1)
        self.wake.set();return {'document_id':doc,'version':1,'job_id':job,'status':'queued'}

    def lease(self,document_id,tenant,owner,seconds=120):
        if not 1<=seconds<=3600:raise ValueError('Lease duration must be 1–3600 seconds')
        with self.db.connect(write=True) as db:
            doc=self._document(db,document_id,tenant,write=True)
            old=db.execute('SELECT * FROM leases WHERE document_id=?',(document_id,)).fetchone()
            if old and old['expires_at']>self.clock():raise Conflict(f"Document is being edited by {old['owner']}")
            token=str(uuid4());fence=(old['fence']+1) if old else 1;expires=self.clock()+seconds
            db.execute('INSERT OR REPLACE INTO leases VALUES(?,?,?,?,?)',(document_id,owner,token,fence,expires))
        return {'token':token,'fence':fence,'expires_at':expires,'base_version':doc['latest_version']}

    def release(self,document_id,tenant,token):
        with self.db.connect(write=True) as db:
            self._document(db,document_id,tenant,write=True)
            db.execute('UPDATE leases SET expires_at=0 WHERE document_id=? AND token=?',(document_id,token))

    def _check_lease(self,db,document_id,token,base_version,latest):
        lease=db.execute('SELECT * FROM leases WHERE document_id=?',(document_id,)).fetchone()
        if not lease or lease['token']!=token or lease['expires_at']<=self.clock():raise Conflict('Write lease is absent, expired or superseded')
        if base_version!=latest:raise Conflict('Document changed; read its latest version before saving')

    def revise(self,document_id,tenant,token,base_version,filename,content):
        suffix=Path(filename).suffix.lower()
        if suffix not in SUPPORTED:raise ValueError('Unsupported file format')
        with self.db.connect(write=True) as db:
            doc=self._document(db,document_id,tenant,write=True)
            self._check_lease(db,document_id,token,base_version,doc['latest_version'])
            version=base_version+1
            directory=self.root/'files'/document_id/f'v{version}';directory.mkdir(exist_ok=True)
            path=directory/('source'+suffix);path.write_bytes(content)
            db.execute('INSERT INTO versions VALUES(?,?,?,?,?,?)',(document_id,version,Path(filename).name,str(path),'queued',self.clock()))
            db.execute('UPDATE documents SET latest_version=? WHERE id=?',(version,document_id))
            db.execute('UPDATE leases SET expires_at=0 WHERE document_id=?',(document_id,))
            job=self._job(db,document_id,version)
            self._event(db,tenant,'document.uploaded',document_id,version)
        self.wake.set();return {'document_id':document_id,'version':version,'job_id':job,'status':'queued'}

    def list_documents(self,tenant):
        with self.db.connect() as db:
            rows=db.execute('''SELECT d.*,v.status FROM documents d LEFT JOIN versions v
                ON v.document_id=d.id AND v.version=d.latest_version
                WHERE d.deleted=0 AND d.tenant IN (?, 'public') ORDER BY d.created_at DESC''',(tenant,)).fetchall()
        return [{**dict(r),'metadata':json.loads(r['metadata'])} for r in rows]

    def document(self,document_id,tenant,version=None):
        with self.db.connect() as db:
            doc=self._document(db,document_id,tenant)
            versions=[{k:v for k,v in dict(r).items() if k!='path'} for r in db.execute('SELECT * FROM versions WHERE document_id=? ORDER BY version DESC',(document_id,))]
            selected=version if version is not None else doc['current_version']
            if version is not None and version not in {v['version'] for v in versions}:raise NotFound('Version not found')
            parents=[dict(r) for r in db.execute('SELECT id,text,section,locator FROM parents WHERE document_id=? AND version=?',(document_id,selected))]
        return {**doc,'metadata':json.loads(doc['metadata']),'versions':versions,'content':parents,'selected_version':selected}

    def original(self,document_id,version,tenant):
        with self.db.connect() as db:
            self._document(db,document_id,tenant)
            r=db.execute('SELECT * FROM versions WHERE document_id=? AND version=?',(document_id,version)).fetchone()
            if not r:raise NotFound('Version not found')
        return dict(r)

    def jobs(self,tenant):
        with self.db.connect() as db:
            return [dict(r) for r in db.execute('''SELECT j.* FROM jobs j JOIN documents d ON d.id=j.document_id
                WHERE d.tenant IN (?, 'public') AND d.deleted=0 ORDER BY j.created_at DESC''',(tenant,))]

    def events(self,tenant,after=0):
        with self.db.connect() as db:
            return [{**dict(r),'payload':json.loads(r['payload'])} for r in db.execute(
                'SELECT * FROM events WHERE id>? AND tenant IN (?,\'public\') ORDER BY id LIMIT 100',(after,tenant))]

    def retry(self,job_id,tenant):
        with self.db.connect(write=True) as db:
            r=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
            if not r:raise NotFound('Job not found')
            doc=self._document(db,r['document_id'],tenant,write=True)
            if r['version']!=doc['latest_version']:raise Conflict('A newer version exists')
            if r['status'] not in {'failed','embedding_failed'}:raise Conflict('Only failed jobs can be retried')
            db.execute("UPDATE jobs SET status='queued',error=NULL,updated_at=? WHERE id=?",(self.clock(),job_id))
        self.wake.set()

    def queue_reindex(self):
        with self.db.connect(write=True) as db:
            count=0
            for r in db.execute('SELECT * FROM documents WHERE deleted=0 AND current_version>0').fetchall():
                if not db.execute("SELECT 1 FROM jobs WHERE document_id=? AND status IN ('queued','running')",(r['id'],)).fetchone():
                    self._job(db,r['id'],r['current_version'],'embed');count+=1
        self.wake.set();return count

    def delete(self,document_id,tenant):
        with self.db.connect(write=True) as db:
            doc=self._document(db,document_id,tenant,write=True)
            db.execute('UPDATE documents SET deleted=1 WHERE id=?',(document_id,))
            db.execute("UPDATE jobs SET status='cancelled' WHERE document_id=? AND status='queued'",(document_id,))
            ids=[r['id'] for r in db.execute('SELECT id FROM chunks WHERE document_id=?',(document_id,))]
            self._event(db,tenant,'document.deleted',document_id,doc['latest_version'])
        self.vectors.remove(ids)

    def process_next(self):
        with self.db.connect(write=True) as db:
            row=db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:return False
            job=dict(row);db.execute("UPDATE jobs SET status='running',updated_at=? WHERE id=?",(self.clock(),job['id']))
        stage='parse'
        try:
            with self.db.connect() as db:
                doc=dict(db.execute('SELECT * FROM documents WHERE id=?',(job['document_id'],)).fetchone())
                version=dict(db.execute('SELECT * FROM versions WHERE document_id=? AND version=?',(doc['id'],job['version'])).fetchone())
            if doc['deleted'] or job['version']!=doc['latest_version']:
                self._finish(job,'superseded');return True
            if job['operation']=='ingest':
                blocks=parse(Path(version['path']))
                if json.loads(doc['metadata']).get('source_kind')=='curated_policy_card':
                    blocks=[b for b in blocks if not b['text'].startswith('TradeX workflow suggestion')]
                parents,children=chunk(blocks,getattr(self.embedding,'split_text',None))
                with self.db.connect(write=True) as db:
                    # A restart repeats parsing, so remove only this unpublished/retried version's chunks.
                    old=[r['id'] for r in db.execute('SELECT id FROM chunks WHERE document_id=? AND version=?',(doc['id'],job['version']))]
                    for cid in old:db.execute('DELETE FROM chunks_fts WHERE chunk_id=?',(cid,))
                    db.execute('DELETE FROM chunks WHERE document_id=? AND version=?',(doc['id'],job['version']))
                    db.execute('DELETE FROM parents WHERE document_id=? AND version=?',(doc['id'],job['version']))
                    for p in parents:db.execute('INSERT INTO parents VALUES(?,?,?,?,?,?)',(p['id'],doc['id'],job['version'],p['text'],p['section'],p['locator']))
                    for c in children:
                        db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?,?,NULL)',(c['id'],doc['id'],job['version'],c['parent_id'],c['text'],c['section'],c['locator']))
                        db.execute('INSERT INTO chunks_fts VALUES(?,?)',(c['id'],' '.join(lexical_tokens(doc['title']+' '+c['text']))))
                    db.execute("UPDATE versions SET status='lexical_ready' WHERE document_id=? AND version=?",(doc['id'],job['version']))
                    db.execute('UPDATE documents SET current_version=? WHERE id=? AND latest_version=? AND deleted=0',(job['version'],doc['id'],job['version']))
                    self._event(db,doc['tenant'],'document.parsed',doc['id'],job['version'],{'chunks':len(children)})
                self.vectors.remove(old)
            else:
                with self.db.connect() as db:children=[dict(r) for r in db.execute('SELECT * FROM chunks WHERE document_id=? AND version=?',(doc['id'],job['version']))]
            stage='embedding'
            vectors=self.embedding.documents([doc['title'][:80]+'\n'+c['text'] for c in children])
            self.vectors.upsert(children,vectors,doc['tenant'],doc['id'],job['version'])
            with self.db.connect(write=True) as db:
                latest=db.execute('SELECT * FROM documents WHERE id=?',(doc['id'],)).fetchone()
                if latest['deleted'] or latest['latest_version']!=job['version']:
                    self.vectors.remove([c['id'] for c in children]);status='superseded'
                else:
                    db.execute('UPDATE chunks SET embedding_model=? WHERE document_id=? AND version=?',(self.embedding.model_id,doc['id'],job['version']))
                    db.execute("UPDATE versions SET status='ready' WHERE document_id=? AND version=?",(doc['id'],job['version']))
                    self._event(db,doc['tenant'],'document.ready',doc['id'],job['version'],{'model':self.embedding.model_id,'chunks':len(children)})
                    status='completed'
                db.execute('UPDATE jobs SET status=?,error=NULL,updated_at=? WHERE id=?',(status,self.clock(),job['id']))
            # Retain old files/SQL revisions for citations; retire their vectors from active search.
            with self.db.connect() as db:
                obsolete=[r['id'] for r in db.execute('SELECT id FROM chunks WHERE document_id=? AND version<>?',(doc['id'],job['version']))]
            if status=='completed':self.vectors.remove(obsolete)
        except Exception as error:
            self._finish(job,'embedding_failed' if stage=='embedding' else 'failed',f'{type(error).__name__}: {error}')
        return True

    def _finish(self,job,status,error=None):
        with self.db.connect(write=True) as db:
            db.execute('UPDATE jobs SET status=?,error=?,updated_at=? WHERE id=?',(status,error,self.clock(),job['id']))
            if status=='failed':db.execute("UPDATE versions SET status='failed' WHERE document_id=? AND version=?",(job['document_id'],job['version']))

    def start_worker(self):
        # The embedded Qdrant process lock ensures one owning service; interrupted jobs are recoverable.
        with self.db.connect(write=True) as db:db.execute("UPDATE jobs SET status='queued' WHERE status='running'")
        def run():
            while not self.stop.is_set():
                if not self.process_next():self.wake.wait(1);self.wake.clear()
        self.worker=threading.Thread(target=run,daemon=True,name='tradex-ingestion');self.worker.start()

    def search(self,query,tenant,market=None,as_of=None,limit=5,mode='hybrid',document_id=None,order_id=None):
        if not query.strip():raise ValueError('Query must not be empty')
        if mode not in {'hybrid','keyword','vector'}:raise ValueError('Unknown retrieval mode')
        as_of=as_of or date.today().isoformat();date.fromisoformat(as_of)
        with self.db.connect() as db:
            rows=db.execute('''SELECT c.*,p.text parent_text,d.title,d.tenant,d.metadata
                FROM chunks c JOIN documents d ON c.document_id=d.id JOIN parents p ON p.id=c.parent_id
                WHERE d.deleted=0 AND c.version=d.current_version AND d.tenant IN (?, 'public')''',(tenant,)).fetchall()
            eligible={}
            for r in rows:
                c=dict(r);m=json.loads(c['metadata']);c['metadata']=m
                if document_id and c['document_id']!=document_id:continue
                if order_id and c['tenant']!='public' and m.get('order_id') not in {None,'',order_id}:continue
                if m.get('allowed_use') in {'historical_reference','monitoring_only','lookup_or_recovery_only'}:continue
                if m.get('effective_from') and m['effective_from']>as_of:continue
                if m.get('effective_to') and m['effective_to']<as_of:continue
                markets={market,'CN','GLOBAL'} | ({'RCEP'} if market in RCEP_MARKETS else set())
                if market and m.get('jurisdiction') and m['jurisdiction'] not in markets:continue
                eligible[c['id']]=c
            tokens=lexical_tokens(query)[:64];lexical=[]
            if mode!='vector' and tokens:
                match=' OR '.join('"'+t+'"' for t in tokens)
                # Filter inside the SQL query, before top-k, so other tenants cannot crowd out local hits.
                lexical=[r['chunk_id'] for r in db.execute('''SELECT f.chunk_id FROM chunks_fts f
                    JOIN chunks c ON c.id=f.chunk_id JOIN documents d ON d.id=c.document_id
                    WHERE chunks_fts MATCH ? AND d.deleted=0 AND c.version=d.current_version
                    AND d.tenant IN (?, 'public') ORDER BY bm25(chunks_fts)''',(match,tenant)) if r['chunk_id'] in eligible][:40]
        vector_ids=[k for k,c in eligible.items() if c['embedding_model']==self.embedding.model_id]
        dense=[];error=None
        if mode!='keyword' and vector_ids:
            try:dense=self.vectors.search(self.embedding.query(query),vector_ids,40)
            except Exception as exc:error=f'{type(exc).__name__}: {exc}'
        scores={}
        for ranking in (lexical,dense):
            for rank,cid in enumerate(ranking,1):scores[cid]=scores.get(cid,0)+1/(60+rank)
        results=[];seen=set()
        for cid in sorted(scores,key=scores.get,reverse=True):
            c=eligible[cid]
            m=c['metadata']
            dedupe=c['document_id'] if m.get('source_kind')=='curated_policy_card' else c['parent_id']
            if dedupe in seen:continue
            seen.add(dedupe)
            results.append({'chunk_id':cid,'document_id':c['document_id'],'version':c['version'],'title':c['title'],
                'text':c['text'],'context':c['parent_text'],'score':round(scores[cid],6),'matched_by':[name for name,ls in [('keyword',lexical),('vector',dense)] if cid in ls],
                'citation':{'locator':c['locator'],'section':c['section'],'source_url':m.get('source_url'),'source_refs':m.get('evidence_refs',[]),
                'original_url':f"/api/documents/{c['document_id']}/versions/{c['version']}/original"},
                'metadata':m,'review_due':bool(m.get('review_due') and m['review_due']<as_of),'trust':'source_data_not_instructions'})
            if len(results)>=limit:break
        return {'query':query,'mode':mode,'embedding_model':self.embedding.model_id,'semantic_available':bool(vector_ids) and not error,
                'semantic_error':error,'results':results,'answer_mode':'retrieved_evidence','as_of':as_of}

    def stats(self,tenant):
        docs=self.list_documents(tenant)
        with self.db.connect() as db:
            r=db.execute('''SELECT COUNT(*) total,SUM(c.embedding_model=?) embedded FROM chunks c JOIN documents d ON d.id=c.document_id
                WHERE d.deleted=0 AND c.version=d.current_version AND d.tenant IN (?, 'public')''',(self.embedding.model_id,tenant)).fetchone()
        return {'documents':len(docs),'ready_documents':sum(d['status']=='ready' for d in docs),'chunks':r['total'],'embedded_chunks':r['embedded'] or 0,
                'embedding_model':self.embedding.model_id,'dimensions':self.embedding.dimensions,'vector_collection':self.embedding.collection,'storage':'SQLite + Qdrant'}

    def close(self):
        self.stop.set();self.wake.set()
        if self.worker:self.worker.join()
        self.vectors.close()
