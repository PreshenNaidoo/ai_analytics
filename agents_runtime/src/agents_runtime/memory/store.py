"""Chroma memory store helpers (client, retrieval, upsert)."""


import hashlib
import os
import re
from datetime import datetime
from typing import Any, TypedDict

import chromadb
from chromadb.utils import embedding_functions

from agents_runtime.structured_outputs import AnalyzeResult, DBCatalogLite


MEMORY_SCHEMA = "schema"
MEMORY_QUERY_PATTERNS = "query_patterns"
MEMORY_SESSION = "session"
ALL_MEMORY_TYPES = (MEMORY_SCHEMA, MEMORY_QUERY_PATTERNS, MEMORY_SESSION)


class MemoryDoc(TypedDict):
    """A single memory record for Chroma upsert."""
    id: str
    doc: str
    meta: dict[str, Any]


def collection_name_for(db_key: str, memory_type: str = MEMORY_QUERY_PATTERNS) -> str:
    """Build a stable collection name from db key and memory type."""
    if memory_type not in ALL_MEMORY_TYPES:
        raise ValueError(f"Unknown memory_type '{memory_type}'. Expected one of {ALL_MEMORY_TYPES}")
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", db_key)[:60]
    return f"ai_analytics__{safe}__{memory_type}"


def stable_fingerprint(*parts: str, size: int = 24) -> str:
    """Create a deterministic short hash from one or more text parts."""
    joined = "||".join((p or "") for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:size]


def normalize_sql_for_fingerprint(sql: str) -> str:
    """Normalize SQL text before hashing to reduce duplicate variants."""
    if not sql:
        return ""
    collapsed = re.sub(r"\s+", " ", sql).strip()
    return collapsed.lower()


def create_chroma_client(path: str | None = None) -> chromadb.PersistentClient:
    """Create a persistent Chroma client at the given path."""
    chroma_dir = path or os.getenv("CHROMA_DIR", ".chroma_ai_analytics")
    os.makedirs(chroma_dir, exist_ok=True)
    return chromadb.PersistentClient(path=chroma_dir)


def create_embedding_function(api_key: str | None = None, model_name: str | None = None):
    """Create an OpenAI embedding function when an API key is available."""
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    model = model_name or os.getenv("CHROMA_OPENAI_EMBED_MODEL", "text-embedding-3-small")
    return embedding_functions.OpenAIEmbeddingFunction(api_key=key, model_name=model)


def get_collection(chroma_client: chromadb.PersistentClient, db_key: str, memory_type: str = MEMORY_QUERY_PATTERNS, embedding_fn=None):
    """Get or create a Chroma collection for one db key and memory type."""
    return chroma_client.get_or_create_collection(
        name=collection_name_for(db_key, memory_type),
        embedding_function=embedding_fn,
        metadata={"db_key": db_key, "memory_type": memory_type},
    )


def rag_retrieve(
    chroma_client: chromadb.PersistentClient,
    db_key: str,
    query: str,
    embedding_fn=None,
    k: int = 8,
    max_chars: int = 2200,
    memory_types: tuple[str, ...] = ALL_MEMORY_TYPES,
) -> str:
    """Retrieve merged context from selected memory collections."""
    docs: list[str] = []
    seen: set[str] = set()
    per_collection_k = max(1, k)

    for memory_type in memory_types:
        col = get_collection(chroma_client, db_key, memory_type, embedding_fn=embedding_fn)
        try:
            res = col.query(query_texts=[query], n_results=per_collection_k)
        except Exception:
            continue
        batch = (res.get("documents") or [[]])[0] or []
        for d in batch:
            if not d or d in seen:
                continue
            seen.add(d)
            docs.append(d)
            if len(docs) >= k:
                return ("\n\n".join(docs))[:max_chars]

    return ("\n\n".join(docs))[:max_chars]


def rag_upsert_docs(
    chroma_client: chromadb.PersistentClient,
    db_key: str,
    memory_type: str,
    items: list[MemoryDoc],
    embedding_fn=None,
) -> None:
    """Upsert generic memory documents into one collection."""
    if not items:
        return
    col = get_collection(chroma_client, db_key, memory_type, embedding_fn=embedding_fn)
    col.upsert(
        ids=[x["id"] for x in items],
        documents=[x["doc"] for x in items],
        metadatas=[x.get("meta", {}) for x in items],
    )


def rag_upsert_catalog(
    chroma_client: chromadb.PersistentClient,
    db_key: str,
    catalog: DBCatalogLite,
    embedding_fn=None,
) -> None:
    """Store discovered schema catalog into schema memory."""
    items: list[MemoryDoc] = []
    now = datetime.utcnow().isoformat()

    for entry in catalog.table_columns:
        t = entry.table
        cols = entry.columns
        items.append(
            {
                "id": f"table::{t}",
                "doc": f"TABLE {t}\nColumns: {', '.join(c.col for c in cols[:120])}",
                "meta": {"type": "table", "table": t, "db_key": db_key, "updated_at": now},
            }
        )

    for e in catalog.eav_hints:
        items.append(
            {
                "id": f"eav::{e.table}",
                "doc": f"EAV_HINT {e.table}\nattribute_cols={e.attribute_cols}\nvalue_cols={e.value_cols}",
                "meta": {"type": "eav_hint", "table": e.table, "db_key": db_key, "updated_at": now},
            }
        )

    rag_upsert_docs(chroma_client, db_key, MEMORY_SCHEMA, items, embedding_fn=embedding_fn)


def rag_upsert_semantics(
    chroma_client: chromadb.PersistentClient,
    db_key: str,
    user_request: str,
    ares: AnalyzeResult,
    catalog: DBCatalogLite | None = None,
    embedding_fn=None,
) -> None:
    """Store SQL patterns and related semantic hints."""
    now = datetime.utcnow().isoformat()
    items: list[MemoryDoc] = []

    for q in ares.sql_appendix:
        sql_fp = stable_fingerprint(q.name, normalize_sql_for_fingerprint(q.sql))
        items.append(
            {
                "id": f"sql::{q.name}::{sql_fp}",
                "doc": f"REQUEST: {user_request}\nQUERY_NAME: {q.name}\nSQL: {q.sql}",
                "meta": {"type": "sql_pattern", "db_key": db_key, "updated_at": now},
            }
        )

    if ares.detail_query:
        dq = ares.detail_query
        detail_fp = stable_fingerprint(dq.name, normalize_sql_for_fingerprint(dq.sql))
        items.append(
            {
                "id": f"detail_sql::{dq.name}::{detail_fp}",
                "doc": f"REQUEST: {user_request}\nDETAIL_QUERY: {dq.name}\nSQL: {dq.sql}",
                "meta": {"type": "detail_sql", "db_key": db_key, "updated_at": now},
            }
        )

    if catalog:
        for ct in catalog.candidate_fact_tables[:5]:
            items.append(
                {
                    "id": f"fact::{ct.name}",
                    "doc": f"FACT_CANDIDATE {ct.name}; confidence={ct.confidence}; why={ct.why}",
                    "meta": {"type": "fact_candidate", "table": ct.name, "db_key": db_key, "updated_at": now},
                }
            )

    rag_upsert_docs(chroma_client, db_key, MEMORY_QUERY_PATTERNS, items, embedding_fn=embedding_fn)


def rag_upsert_session_turn(
    chroma_client: chromadb.PersistentClient,
    db_key: str,
    user_request: str,
    user_output: str,
    embedding_fn=None,
) -> None:
    """Store one user request and assistant answer in session memory."""
    now = datetime.utcnow().isoformat()
    req = (user_request or "").strip()
    out = (user_output or "").strip()
    if not req or not out:
        return

    turn_id = stable_fingerprint(req, out)
    item: MemoryDoc = {
        "id": f"session::{turn_id}",
        "doc": f"REQUEST: {req}\nASSISTANT: {out}",
        "meta": {"type": "session_turn", "db_key": db_key, "updated_at": now},
    }
    rag_upsert_docs(chroma_client, db_key, MEMORY_SESSION, [item], embedding_fn=embedding_fn)
