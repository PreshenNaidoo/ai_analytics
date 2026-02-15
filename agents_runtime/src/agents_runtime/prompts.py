"""Prompt loading utilities."""


from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    prompts_dir = Path(__file__).resolve().parent / "prompts"
    p = prompts_dir / f"{name}.md"
    return p.read_text(encoding="utf-8").strip()
