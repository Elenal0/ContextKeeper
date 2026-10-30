"""Unit tests for Context-Loss Risk scoring engine (Pure functions, no DB)."""
from datetime import datetime, timedelta, timezone

from app.db.models import ActionItem, Availability, ItemStatus, Participant, Person, Priority, RSVP
from app.services.risk import compute_item_risk, compute_meeting_risk


def test_closed_or_cancelled_items_have_zero_risk():
    item_done = ActionItem(title="Done task", status=ItemStatus.done)
    item_cancelled = ActionItem(title="Cancelled task", status=ItemStatus.cancelled)
    
    score_done, signals_done = compute_item_risk(item_done)
    score_cancelled, signals_cancelled = compute_item_risk(item_cancelled)
    
    assert score_done == 0
    assert signals_done == []
    assert score_cancelled == 0
    assert signals_cancelled == []


def test_unassigned_item_fires_signal():
    item = ActionItem(title="Unassigned task", status=ItemStatus.open, owner_id=None)
    score, signals = compute_item_risk(item, owner=None)
    
    assert score >= 20
    assert any(s["signal"] == "no_owner" for s in signals)


def test_overdue_item_and_owner_on_leave():
    now = datetime.now(timezone.utc)
    owner_leave = Person(name="Alex", email="a@x.com", availability=Availability.on_leave)
    item = ActionItem(
        title="Critical DB task",
        status=ItemStatus.open,
        owner_id=1,
        due_date=now - timedelta(days=2),
    )

    score, signals = compute_item_risk(item, owner=owner_leave, now=now)
    # Overdue (25) + owner_on_leave (20) + no_kb_link (5) = at least 50
    assert score >= 45
    assert any(s["signal"] == "overdue" for s in signals)
    assert any(s["signal"] == "owner_on_leave" for s in signals)


def test_owner_missed_source_meeting():
    now = datetime.now(timezone.utc)
    owner = Person(name="Bob", email="b@x.com", availability=Availability.available)
    item = ActionItem(
        title="Review PR",
        status=ItemStatus.open,
        owner_id=2,
        source_meeting_id=10,
    )
    part_no_show = [Participant(meeting_id=10, person_id=2, rsvp=RSVP.no_response)]

    score, signals = compute_item_risk(item, owner=owner, source_participants=part_no_show, now=now)
    assert any(s["signal"] == "owner_missed_meeting" for s in signals)


def test_carried_forward_multiple_times():
    now = datetime.now(timezone.utc)
    owner = Person(name="Alice", email="alice@x.com", availability=Availability.available)
    item = ActionItem(
        title="Stale carry forward item",
        status=ItemStatus.open,
        owner_id=3,
        carry_forward_count=4,
    )

    score, signals = compute_item_risk(item, owner=owner, now=now)
    assert any(s["signal"] == "carried_forward_many" for s in signals)


def test_risk_score_is_capped_at_100():
    now = datetime.now(timezone.utc)
    owner = Person(name="Alex", email="a@x.com", availability=Availability.on_leave)
    item = ActionItem(
        title="Everything wrong task",
        status=ItemStatus.blocked,
        owner_id=1,
        due_date=now - timedelta(days=10),
        carry_forward_count=5,
    )
    part = [Participant(meeting_id=1, person_id=1, rsvp=RSVP.absent)]

    score, signals = compute_item_risk(
        item=item,
        owner=owner,
        source_participants=part,
        has_kb_link=False,
        days_since_updated=15,
        has_unnoted_reassignment=True,
        now=now,
    )
    assert score == 100
    assert len(signals) >= 6


def test_compute_meeting_risk_aggregation():
    risk = compute_meeting_risk(
        items_risk_scores=[80, 50, 20],
        total_participants=5,
        absent_count=2,
    )
    # Average = 50, Max = 80 -> base = 68. Absent ratio = 2/5 -> +10. Total ~ 78
    assert 65 <= risk <= 85

