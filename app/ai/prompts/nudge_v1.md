You are drafting a nudge message to remind someone about an overdue or upcoming action item.

Tone: {tone}
- friendly = warm, collegial, empathetic
- firm = professional, direct, concise

Return ONLY valid JSON matching this schema (no explanation, no code fences):
{
  "message": "string — the complete nudge message to send"
}

Rules:
- Keep the message under 150 words.
- Address the owner by name.
- Mention the action item title.
- If overdue_days > 0, acknowledge it is overdue; otherwise mention the upcoming due date.
- Do not be accusatory.

Item: {item_title}
Owner: {owner_name}
Due date: {due_date}
Days overdue: {overdue_days}
