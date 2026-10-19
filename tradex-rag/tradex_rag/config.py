import os
from dataclasses import dataclass, field
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv('TRADEX_DATA_DIR', ROOT / 'var')))
    model_dir: Path = field(default_factory=lambda: ROOT / '.models')
    embedding: str = field(default_factory=lambda: os.getenv('TRADEX_EMBEDDING', 'bge-local'))
    tenant: str = field(default_factory=lambda: os.getenv('TRADEX_TENANT', 'demo-exporter'))
    actor: str = field(default_factory=lambda: os.getenv('TRADEX_ACTOR', 'local-user'))
    qdrant_url: str | None = field(default_factory=lambda: os.getenv('QDRANT_URL'))
