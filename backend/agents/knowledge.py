"""Agente de Conocimiento: búsqueda en una base de artículos local."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

DEFAULT_KB = Path(__file__).with_name("kb_articles.json")


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    category: str
    keywords: tuple[str, ...]
    summary: str


class KnowledgeBase:
    """Puntúa artículos por palabras clave coincidentes y por categoría."""

    def __init__(self, articles: list[Article]) -> None:
        self.articles = articles

    @classmethod
    def load(cls, path: Path | str = DEFAULT_KB) -> KnowledgeBase:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        return cls(
            [
                Article(
                    id=a["id"],
                    title=a["title"],
                    category=a.get("category", "general"),
                    keywords=tuple(_norm(k) for k in a.get("keywords", [])),
                    summary=a.get("summary", ""),
                )
                for a in raw
            ]
        )

    def search(self, text: str, category: str | None = None, min_score: int = 1) -> Article | None:
        words = set(re.findall(r"\w+", _norm(text)))
        joined = _norm(text)
        best: tuple[int, Article] | None = None
        for article in self.articles:
            score = sum(1 for k in article.keywords if (k in words or (" " in k and k in joined)))
            if score == 0:
                continue
            if category and article.category == category:
                score += 1
            if best is None or score > best[0]:
                best = (score, article)
        if best is None or best[0] < min_score:
            return None
        return best[1]
