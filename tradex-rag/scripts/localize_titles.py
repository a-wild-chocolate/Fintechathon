"""Refresh English policy titles in an existing local library."""
import json
import sqlite3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
titles = json.loads((root.parent / 'knowledge_base/titles_en.json').read_text())
database = root / 'var/library.sqlite3'
if database.exists():
    with sqlite3.connect(database) as db:
        for key, title in titles.items():
            row = db.execute('SELECT id,metadata FROM documents WHERE source_key=? AND tenant=?', (key, 'public')).fetchone()
            if row:
                metadata = json.loads(row[1])
                metadata['title_en'] = title
                db.execute('UPDATE documents SET metadata=? WHERE id=?', (json.dumps(metadata, ensure_ascii=False), row[0]))
    print(f'English titles refreshed from {len(titles)} policy cards.')
else:
    print('No local library yet. The seed command imports English titles automatically.')
