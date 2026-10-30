"""
Deterministic fallback extractor.

Used when AI is unavailable. Extracts action items, decisions, and summary
from raw text using simple heuristics — no AI required.
"""
from __future__ import annotations

import re
from datetime import datetime


# Regex patterns
_TODO_PATTERN = re.compile(
    r"^[\s\-\*•]*(?:TODO|Action|AI|Action Item|Task|@\w+)[\s:]+(.+)",
    re.IGNORECASE | re.MULTILINE,
)
_OWNER_PATTERN = re.compile(r"@(\w[\w.]+)")
_DATE_PATTERN = re.compile(
    r"\b(?:by|due|before|deadline)\s+(\w+\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)",
    re.IGNORECASE,
)
_DECISION_PATTERN = re.compile(
    r"^[\s\-\*•]*(?:DECIDED|Decision|We will|Agreed|Confirmed|Resolved)[\s:]+(.+)",
    re.IGNORECASE | re.MULTILINE,
)
_BULLET_PATTERN = re.compile(
    r"^[\s]*[-•*]\s+(.+)",
    re.MULTILINE,
)


def extract_action_items_heuristic(text: str) -> list[dict]:
    """
    Extract action items from raw text using heuristics.

    Detects lines starting with: TODO, Action:, AI:, @name, bullet points.
    Extracts @owner and 'by <date>' patterns.
    """
    items: list[dict] = []
    seen_titles: set[str] = set()

    # Try TODO/Action patterns first
    for match in _TODO_PATTERN.finditer(text):
        title = match.group(1).strip()
        if not title or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())

        # Extract owner from @mention
        owner_match = _OWNER_PATTERN.search(title)
        owner = owner_match.group(1) if owner_match else None

        # Extract due date
        date_match = _DATE_PATTERN.search(title)
        due_date = date_match.group(1) if date_match else None

        items.append({
            "title": title,
            "description": "",
            "owner": owner,
            "due_date": due_date,
            "priority": "medium",
            "confidence": 0.6,
            "source_quote": title[:100],
        })

    # Also extract bullet points
    for match in _BULLET_PATTERN.finditer(text):
        title = match.group(1).strip()
        if not title or len(title) < 5 or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())

        owner_match = _OWNER_PATTERN.search(title)
        owner = owner_match.group(1) if owner_match else None
        date_match = _DATE_PATTERN.search(title)
        due_date = date_match.group(1) if date_match else None

        items.append({
            "title": title[:200],
            "description": "",
            "owner": owner,
            "due_date": due_date,
            "priority": "medium",
            "confidence": 0.4,
            "source_quote": title[:100],
        })

    return items[:20]  # cap at 20


def extract_decisions_heuristic(text: str) -> list[str]:
    """Extract decision statements from raw text."""
    decisions = []
    for match in _DECISION_PATTERN.finditer(text):
        decision = match.group(1).strip()
        if decision and decision not in decisions:
            decisions.append(decision[:300])
    return decisions[:10]


def extract_summary_heuristic(text: str) -> str:
    """Return the first ~3 meaningful sentences as a summary."""
    # Split on sentence endings
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    # Filter out very short or header-like lines
    meaningful = [
        s.strip() for s in sentences
        if len(s.strip()) > 20 and not s.strip().startswith("#")
    ]
    return " ".join(meaningful[:3]) if meaningful else text[:300]


def extract_open_questions_heuristic(text: str) -> list[str]:
    """Extract lines ending with ? as open questions."""
    questions = []
    for line in text.splitlines():
        line = line.strip()
        if line.endswith("?") and len(line) > 10:
            questions.append(line[:200])
    return questions[:10]
