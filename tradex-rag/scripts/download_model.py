"""Download public model files once; normal local inference uses only this cache."""
from pathlib import Path
from fastembed import TextEmbedding
root=Path(__file__).resolve().parents[1]
m=TextEmbedding('BAAI/bge-small-zh-v1.5',cache_dir=str(root/'.models'),threads=2)
print('Downloaded BGE model. Vector dimensions:',len(list(m.embed(['外贸付款条款']))[0]))
