"""
Risk Radar scoring engine — deterministic Context-Loss Risk Score (0-100).

Pure functions: unit-testable without database or AI dependencies.
The AI only explains or suggests actions; the score is 100% transparent and deterministic.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.db.models import ActionItem, Availability, ItemStatus, Participant, Person, RSVP


RISK_WEIGHTS = {
    "overdue": 25,
    "due_soon": 10,               # due in <= 3 days
    "no_owner": 20,
    "owner_on_leave": 20,
    "owner_missed_meeting": 15,   # invited, no_response, declined, or absent
    "carried_forward_many": 15,   # carried forward >= 3 times
    "carried_forward_some": 5,    # carried forward 1-2 times
    "blocked": 15,
    "no_kb_link": 5,
    "no_recent_activity": 10,     # no update in > 7 days
    "reassigned_no_note": 10,     # owner changed with empty/no note
}


def compute_item_risk(
    item: ActionItem,
    owner: Person | None = None,
    source_participants: list[Participant] | None = None,
    has_kb_link: bool = False,
    days_since_updated: int = 0,
    has_unnoted_reassignment: bool = False,
    now: datetime | None = None,
) -> tuple[int, list[dict[str, str]]]:
    """
    Compute a context-loss risk score (0-100) and list of fired signals for an action item.

    Pure function: all inputs are explicitly passed.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Closed or cancelled items have 0 risk
    if item.status in (ItemStatus.done, ItemStatus.cancelled):
        return 0, []

    score = 0
    signals: list[dict[str, str]] = []

    # 1. Overdue or due soon
    if item.due_date:
        due = item.due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        diff_seconds = (due - now).total_seconds()
        diff_days = diff_seconds / 86400.0

        if diff_days < 0:
            score += RISK_WEIGHTS["overdue"]
            days_over = abs(int(diff_days))
            signals.append({
                "signal": "overdue",
                "description": f"Overdue by {days_over} day{'s' if days_over != 1 else ''}",
            })
        elif diff_days <= 3:
            score += RISK_WEIGHTS["due_soon"]
            days_left = max(0, int(diff_days))
            signals.append({
                "signal": "due_soon",
                "description": f"Due soon (in {days_left} day{'s' if days_left != 1 else ''})",
            })

    # 2. Owner checks
    if not item.owner_id or owner is None:
        score += RISK_WEIGHTS["no_owner"]
        signals.append({
            "signal": "no_owner",
            "description": "Unassigned: no owner allocated to this item",
        })
    else:
        # Owner on leave
        if owner.availability == Availability.on_leave:
            score += RISK_WEIGHTS["owner_on_leave"]
            leave_info = f" ({owner.leave_start.strftime('%b %d') if owner.leave_start else ''} - {owner.leave_end.strftime('%b %d') if owner.leave_end else ''})" if owner.leave_start or owner.leave_end else ""
            signals.append({
                "signal": "owner_on_leave",
                "description": f"Owner {owner.name} is currently on leave{leave_info}",
            })

        # Owner attendance in source meeting
        if source_participants:
            for p in source_participants:
                if p.person_id == item.owner_id:
                    if p.rsvp in (RSVP.no_response, RSVP.declined, RSVP.absent, RSVP.invited):
                        score += RISK_WEIGHTS["owner_missed_meeting"]
                        signals.append({
                            "signal": "owner_missed_meeting",
                            "description": f"Owner {owner.name} did not attend source meeting (RSVP: {p.rsvp})",
                        })
                    break

    # 3. Carried forward count
    carry_count = item.carry_forward_count or 0
    if carry_count >= 3:
        score += RISK_WEIGHTS["carried_forward_many"]
        signals.append({
            "signal": "carried_forward_many",
            "description": f"Stale context: carried forward {carry_count} times across meetings",
        })
    elif carry_count >= 1:
        score += RISK_WEIGHTS["carried_forward_some"]
        signals.append({
            "signal": "carried_forward_some",
            "description": f"Carried forward {carry_count} time(s)",
        })

    # 4. Status: blocked
    if item.status == ItemStatus.blocked:
        score += RISK_WEIGHTS["blocked"]
        signals.append({
            "signal": "blocked",
            "description": "Item is marked as blocked and waiting for resolution",
        })

    # 5. Knowledge base linkage
    if not has_kb_link:
        score += RISK_WEIGHTS["no_kb_link"]
        signals.append({
            "signal": "no_kb_link",
            "description": "No documentation or KB runbook linked for guidance",
        })

    # 6. Staleness / lack of recent activity
    if days_since_updated >= 7:
        score += RISK_WEIGHTS["no_recent_activity"]
        signals.append({
            "signal": "no_recent_activity",
            "description": f"No status updates or notes in {days_since_updated} days",
        })

    # 7. Reassigned with no handover note
    if has_unnoted_reassignment:
        score += RISK_WEIGHTS["reassigned_no_note"]
        signals.append({
            "signal": "reassigned_no_note",
            "description": "Owner was changed without an accompanying handover note",
        })

    final_score = min(100, max(0, score))
    return final_score, signals


def compute_meeting_risk(
    items_risk_scores: list[int],
    total_participants: int,
    absent_count: int,
) -> int:
    """
    Compute aggregate risk score for a meeting / handover (0-100).
    Factors in maximum item risk, average item risk, and participant absenteeism.
    """
    if not items_risk_scores:
        meeting_risk = 0
    else:
        avg_risk = sum(items_risk_scores) / len(items_risk_scores)
        max_risk = max(items_risk_scores)
        meeting_risk = int(0.6 * max_risk + 0.4 * avg_risk)

    if total_participants > 0 and absent_count > 0:
        absent_ratio = absent_count / total_participants
        meeting_risk += int(absent_ratio * 25)

    return min(100, max(0, meeting_risk))
