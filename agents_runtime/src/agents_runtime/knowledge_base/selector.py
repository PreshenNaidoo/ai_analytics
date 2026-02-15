"""Knowledge base folder and candidate file selection."""


import os
import re
from typing import Any

from agents_runtime.config import RuntimeSettings


def kb_safe_key(db_key: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", db_key)[:80]


def get_kb_paths(db_key: str, settings: RuntimeSettings) -> dict[str, str]:
    base_dir = os.path.abspath(settings.knowledge_base_dir)
    shared_dir = os.path.join(base_dir, settings.shared_docs_subdir)
    db_dir = os.path.join(base_dir, kb_safe_key(db_key))
    os.makedirs(shared_dir, exist_ok=True)
    os.makedirs(db_dir, exist_ok=True)
    return {
        "knowledge_base_dir": base_dir,
        "knowledge_base_shared_dir": shared_dir,
        "knowledge_base_db_dir": db_dir,
    }


def tokenize_for_match(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z0-9_]+", (text or "").lower()) if len(t) >= 3]


def iter_kb_files(root_dir: str, allowed_extensions: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    if not os.path.isdir(root_dir):
        return out
    for root, _, files in os.walk(root_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in allowed_extensions:
                out.append(os.path.join(root, f))
    return out


def build_kb_context(db_key: str, user_prompt: str, settings: RuntimeSettings, max_files: int | None = None) -> dict[str, Any]:
    paths = get_kb_paths(db_key, settings)
    max_files = max_files or settings.max_kb_candidate_files
    db_files = iter_kb_files(paths["knowledge_base_db_dir"], settings.kb_allowed_extensions)
    shared_files = iter_kb_files(paths["knowledge_base_shared_dir"], settings.kb_allowed_extensions)

    tokens = set(tokenize_for_match(user_prompt))

    def score(path: str) -> tuple[int, int, str]:
        base = os.path.basename(path).lower()
        name_score = sum(1 for t in tokens if t in base)
        db_boost = 1 if path.startswith(paths["knowledge_base_db_dir"]) else 0
        return (name_score, db_boost, base)

    ranked = sorted(db_files + shared_files, key=score, reverse=True)
    selected = ranked[:max_files]
    primary = selected[:5]

    return {
        **paths,
        "knowledge_base_primary_files": primary,
        "knowledge_base_candidate_files": selected,
    }
