import threading
from qdrant_client import QdrantClient,models
class VectorStore:
    def __init__(self,settings,embedding):
        self.lock=threading.RLock();self.collection=embedding.collection
        self.client=QdrantClient(url=settings.qdrant_url) if settings.qdrant_url else QdrantClient(path=str(settings.data_dir/'qdrant'))
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(self.collection,vectors_config=models.VectorParams(size=embedding.dimensions,distance=models.Distance.COSINE))
    def upsert(self,chunks,vectors,tenant,document_id,version):
        points=[models.PointStruct(id=c['id'],vector=v,payload={'tenant':tenant,'document_id':document_id,'version':version}) for c,v in zip(chunks,vectors,strict=True)]
        with self.lock:
            if points:self.client.upsert(self.collection,points=points,wait=True)
    def search(self,vector,eligible_ids,limit=30):
        if not eligible_ids:return []
        with self.lock:
            r=self.client.query_points(self.collection,query=vector,
                query_filter=models.Filter(must=[models.HasIdCondition(has_id=eligible_ids)]),limit=limit)
        return [str(p.id) for p in r.points]
    def remove(self,ids):
        if ids:
            with self.lock:self.client.delete(self.collection,models.PointIdsList(points=ids),wait=True)
    def close(self):self.client.close()
