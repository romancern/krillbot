import sqlite3
from datetime import datetime, timezone


# Puffer Party's client ranks these observed tiers in this order.
PUFFER_TIERS = {'plankton': 0, 'tooclever': 0, 'schooler': 1,
                'rare': 2, 'deepcut': 3, 'krillion': 4}


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('''CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY, question TEXT NOT NULL, mode TEXT NOT NULL,
            answer TEXT NOT NULL, status TEXT NOT NULL, source TEXT NOT NULL,
            score REAL, rarity TEXT, timestamp TEXT NOT NULL)''')
        self.db.commit()

    def record(self, question, mode, answer, status, source, score=None, rarity=None):
        if status not in {'accepted', 'rejected', 'observed', 'suggested', 'inferred'}:
            raise ValueError('Invalid status')
        if not all(x.strip() for x in (question, mode, answer, source)):
            raise ValueError('Question, mode, answer and source are required')
        if (score is not None or rarity is not None) and status not in {'accepted', 'rejected', 'observed'}:
            raise ValueError('Score and rarity require an observed result')
        self.db.execute('INSERT INTO observations (question, mode, answer, status, source, score, rarity, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (question, mode, answer, status, source, score, rarity, datetime.now(timezone.utc).isoformat()))
        self.db.commit()

    def lookup(self, question, mode, used=()):
        rows = self.db.execute('SELECT * FROM observations WHERE question = ? AND mode = ? ORDER BY id DESC', (question, mode)).fetchall()
        excluded = {x.strip().casefold() for x in used}
        groups = {}
        for row in rows:
            key = row['answer'].strip().casefold()
            if key not in excluded:
                groups.setdefault(key, []).append(row)
        # Prefer accepted answers, then the highest known observed Puffer Party tier.
        # Other modes and unrecognized labels have no inferred ordering.
        def rank(group):
            decisive = next((r for r in group if r['status'] in ('accepted', 'rejected')), None)
            status = decisive['status'] if decisive else group[0]['status']
            tier = -1
            if status == 'accepted' and mode == 'puffer-party':
                evidence = next((r for r in group if r['status'] in ('accepted', 'observed')
                                 and r['rarity'] and r['rarity'].lower() in PUFFER_TIERS), None)
                if evidence:
                    tier = PUFFER_TIERS[evidence['rarity'].lower()]
            return ({'accepted': 0, 'observed': 1, 'suggested': 2, 'inferred': 3, 'rejected': 4}[status], -tier)
        return sorted(groups.values(), key=rank)
