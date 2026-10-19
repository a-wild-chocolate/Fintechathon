import os, threading
import httpx

class LocalBGE:
    model_id='BAAI/bge-small-zh-v1.5'
    dimensions=512
    collection='tradex_bge_small_zh_v15_512'
    def __init__(self,model_dir):
        self.model_dir=model_dir;self._model=None;self._tokenizer=None;self.lock=threading.RLock()
    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding
            self._model=TextEmbedding(self.model_id,cache_dir=str(self.model_dir),threads=2,local_files_only=True)
        return self._model
    def split_text(self,text):
        # Use the actual BGE tokenizer, leaving room for the document title.
        with self.lock:
            if self._tokenizer is None:
                from tokenizers import Tokenizer
                model=self._load().model
                model._ensure_tokenizer()
                self._tokenizer=Tokenizer.from_str(model.tokenizer.to_str())
                self._tokenizer.no_truncation();self._tokenizer.no_padding()
            offsets=self._tokenizer.encode(text,add_special_tokens=False).offsets
        start=0
        while start<len(offsets):
            stop=min(start+350,len(offsets))
            candidate=text[offsets[start][0]:offsets[stop-1][1]]
            # Starting inside a word can change WordPiece segmentation; check the actual substring.
            while len(self._tokenizer.encode(candidate,add_special_tokens=False).ids)>350:
                stop-=1;candidate=text[offsets[start][0]:offsets[stop-1][1]]
            yield candidate
            if stop==len(offsets):break
            start=max(start+1,stop-50)
    def documents(self,texts):
        with self.lock:return [v.tolist() for v in self._load().embed(texts,batch_size=16)]
    def query(self,text):
        with self.lock:return list(self._load().query_embed(text))[0].tolist()

class DashScope:
    def __init__(self):
        self.model_id=os.getenv('TRADEX_EMBEDDING_MODEL','text-embedding-v4')
        self.dimensions=int(os.getenv('TRADEX_EMBEDDING_DIMENSIONS','1024'))
        self.collection=f'tradex_{self.model_id.replace("-","_")}_{self.dimensions}'
    def documents(self,texts):
        key=os.getenv('DASHSCOPE_API_KEY');base=os.getenv('DASHSCOPE_BASE_URL')
        if not key or not base:raise RuntimeError('Set DASHSCOPE_API_KEY and DASHSCOPE_BASE_URL before indexing with DashScope.')
        vectors=[]
        for start in range(0,len(texts),16):
            response=httpx.post(base.rstrip('/')+'/embeddings',headers={'Authorization':f'Bearer {key}'},
                json={'model':self.model_id,'input':texts[start:start+16],'dimensions':self.dimensions,'encoding_format':'float'},timeout=60)
            response.raise_for_status()
            batch=sorted(response.json()['data'],key=lambda x:x['index'])
            if len(batch)!=len(texts[start:start+16]):raise ValueError('Embedding response count does not match input count')
            if any(len(v['embedding'])!=self.dimensions for v in batch):raise ValueError('Embedding dimension mismatch')
            vectors.extend(v['embedding'] for v in batch)
        return vectors
    def query(self,text):return self.documents([text])[0]

class NoEmbedding:
    model_id='none';dimensions=512;collection='tradex_pending_512'
    def documents(self,texts):raise RuntimeError('Embedding disabled; keyword retrieval remains available.')
    def query(self,text):raise RuntimeError('Embedding disabled')

def provider(settings):
    if settings.embedding=='bge-local':return LocalBGE(settings.model_dir)
    if settings.embedding=='dashscope':return DashScope()
    if settings.embedding=='none':return NoEmbedding()
    raise ValueError('TRADEX_EMBEDDING must be bge-local, dashscope or none')
