"""KB Linking AI task with TF-IDF candidate retrieval and LLM reranking."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import Any

from app.ai.runner import run_ai


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer, lowercased."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _tfidf_score(query_tokens: list[str], doc_text: str, corpus_doc_count: int, doc_freq: dict[str, int]) -> float:
    """Compute TF-IDF score for a single document."""
    doc_tokens = _tokenize(doc_text)
    if not doc_tokens:
        return 0.0
    doc_len = len(doc_tokens)
    doc_token_counts = Counter(doc_tokens)
    score = 0.0
    for token in set(query_tokens):
        tf = doc_token_counts.get(token, 0) / doc_len
        df = doc_freq.get(token, 0)
        idf = math.log((corpus_doc_count + 1) / (df + 1)) + 1.0
        score += tf * idf
    return score


def tfidf_rank(query: str, kb_docs: list[dict[str, Any]], top_k: int = 10) -> list[dict[str, Any]]:
    """
    Rank KB docs by TF-IDF against query.
    kb_docs: list of {"id": int, "title": str, "content": str, ...}
    Returns top_k docs sorted by score descending.
    """
    query_tokens = _tokenize(query)
    if not query_tokens or not kb_docs:
        return kb_docs[:top_k]

    # Build document frequency map across corpus
    doc_freq: dict[str, int] = Counter()
    for doc in kb_docs:
        text = f"{doc.get('title', '')} {doc.get('content', '')}"
        for token in set(_tokenize(text)):
            doc_freq[token] += 1

    n = len(kb_docs)
    scored = []
    for doc in kb_docs:
        text = f"{doc.get('title', '')} {doc.get('content', '')}"
        score = _tfidf_score(query_tokens, text, n, doc_freq)
        scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


async def generate_kb_links(
    context_text: str,
    kb_candidates: list[dict[str, Any]],
    meeting_id: int | None,
    item_id: int | None,
    db,
) -> list[dict[str, Any]]:
    """
    Generate KB links for given context.
    1. TF-IDF candidate retrieval to narrow to top 10
    2. LLM reranking of candidates
    Returns list of {"kb_doc_id", "relevance_score", "reason"}.
    """
    if not kb_candidates:
        return []

    # Step 1: TF-IDF narrowing
    candidates = tfidf_rank(context_text, kb_candidates, top_k=10)

    # Format candidates for LLM
    candidates_text = json.dumps(
        [{"id": d.get("id"), "title": d.get("title"), "content": (d.get("content") or "")[:300]} for d in candidates],
        indent=2,
    )

    result, ai_run = await run_ai(
        feature="kb_link",
        prompt_name="kb_link",
        prompt_version="v1",
        variables={
            "context_text": context_text[:3000],
            "kb_candidates": candidates_text,
        },
        db=db,
    )

    if result.get("_fallback"):
        # Fallback: return TF-IDF results with default score
        return [
            {
                "kb_doc_id": d.get("id"),
                "relevance_score": 0.4,
                "reason": "TF-IDF candidate (AI unavailable)",
            }
            for d in candidates[:5]
        ]

    links = result.get("links", [])
    # Filter for score > 0.3 and ensure kb_doc_id is valid
    valid_ids = {d.get("id") for d in candidates}
    filtered = [
        lnk for lnk in links
        if isinstance(lnk, dict)
        and lnk.get("relevance_score", 0) > 0.3
        and lnk.get("kb_doc_id") in valid_ids
    ]
    filtered.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return filtered
