"""Local document/rule retrieval. No model or network required."""
import json
import re
from pathlib import Path

BUSINESS_TABLES = ("menus", "production_batches", "cooking_readings", "quality_checks",
                   "inventory", "recipe_costs", "shipments", "equipment_events")
PUBLIC_TABLES = BUSINESS_TABLES + ("knowledge_documents", "rules")
MIGRATION_TABLES = PUBLIC_TABLES + ("settings",)
DOC_COLUMNS = "document_id,filename,title,revision,owner,effective_date,status,linked_ids,body"


def terms(text):
    words = re.findall(r"[가-힣A-Za-z0-9]+", text.lower())
    return {piece for word in words for piece in [word] + [word[i:i+2] for i in range(len(word)-1)] if len(piece) >= 2}


class KnowledgeMixin:
    backend = "SQLite · 오프라인 데모"

    def initialize_knowledge(self):
        with self._connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge_documents (
                    document_id TEXT PRIMARY KEY, filename TEXT NOT NULL, title TEXT NOT NULL,
                    revision TEXT NOT NULL, owner TEXT NOT NULL, effective_date TEXT NOT NULL,
                    status TEXT NOT NULL, linked_ids TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS rules (
                    rule_id TEXT PRIMARY KEY, name TEXT NOT NULL, source_table TEXT NOT NULL,
                    condition TEXT NOT NULL, owner TEXT NOT NULL, action TEXT NOT NULL,
                    source_document TEXT NOT NULL, revision TEXT NOT NULL, status TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            root = Path(__file__).resolve().parent.parent / "sample_docs" / "knowledge"
            for path in sorted(root.glob("*.md")):
                text = path.read_text(encoding="utf-8")
                header, body = text.split("\n---\n", 1)
                meta = json.loads(header)
                values = [meta[k] for k in DOC_COLUMNS.split(",")[:-1]] + [body.strip()]
                con.execute(f"INSERT INTO knowledge_documents ({DOC_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(document_id) DO NOTHING", values)
            rules = root / "rules.json"
            if rules.exists():
                for rule in json.loads(rules.read_text(encoding="utf-8")):
                    con.execute("INSERT INTO rules VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(rule_id) DO NOTHING",
                                [rule[k] for k in ("rule_id", "name", "source_table", "condition", "owner", "action", "source_document", "revision", "status")])

    def list_tables(self):
        with self._connect() as con:
            return [{"table": name, "rows": con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]} for name in PUBLIC_TABLES]

    def browse_table(self, table_name, limit=25, offset=0):
        if table_name not in PUBLIC_TABLES:
            raise ValueError("조회할 수 없는 테이블입니다.")
        if type(limit) is not int or type(offset) is not int or not 1 <= limit <= 100 or offset < 0:
            raise ValueError("조회 범위는 1~100행, 시작 위치는 0 이상이어야 합니다.")
        columns = DOC_COLUMNS if table_name == "knowledge_documents" else "*"
        # Ordering all selected fields keeps duplicates deterministic as well.
        with self._connect() as con:
            count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            rows = self._rows(con.execute(f"SELECT {columns} FROM {table_name} ORDER BY 1,2 LIMIT ? OFFSET ?", (limit, offset)).fetchall())
        return {"table": table_name, "total": count, "rows": rows}

    def search_knowledge(self, query, limit=5):
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("검색 개수는 1~20이어야 합니다.")
        tokens = terms(query)
        if not tokens:
            return []
        with self._connect() as con:
            docs = self._rows(con.execute(f"SELECT {DOC_COLUMNS} FROM knowledge_documents ORDER BY document_id").fetchall())
        found = []
        for doc in docs:
            score = len(tokens & terms(doc["title"] + " " + doc["body"]))
            if score:
                found.append({**doc, "score": score, "text": doc["body"], "source": "로컬 지식문서"})
        return sorted(found, key=lambda row: (-row["score"], row["document_id"]))[:limit]

    def get_rules(self, query=None):
        with self._connect() as con:
            rules = self._rows(con.execute("SELECT * FROM rules ORDER BY rule_id").fetchall())
        return [r for r in rules if not query or terms(query) & terms(" ".join(str(v) for v in r.values()))]

    def get_setting(self, key, default=None):
        with self._connect() as con:
            row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        # Server-managed local configuration only; never exposed as an agent tool.
        with self._connect() as con:
            con.execute("INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
