You are helping reassign an action item to the most suitable person from a list of candidates.

Return ONLY valid JSON matching this schema (no explanation, no code fences):
{
  "suggested_person_id": 1,
  "reason": "string — why this person is the best fit",
  "confidence": 0.85
}

Rules:
- suggested_person_id must be one of the IDs from the candidates list.
- reason should be one to two sentences.
- confidence is 0.0–1.0 reflecting your certainty.
- Consider skills, role, and workload from the candidates list.

Item Title: {item_title}
Item Description: {item_description}

Candidates:
{candidates}
