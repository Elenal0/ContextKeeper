"""
ContextKeeper Database Seed Script (`python -m app.seed`).

Creates realistic, self-authored data:
- 6 people with specific roles and availability (one on medical leave)
- 6 meetings and 2 work transfers spanning 3 weeks
- Real unstructured raw notes (Slack dump, transcript with timestamps, messy email thread)
- 25 action items in various states (open, in_progress, blocked, done, cancelled) with append-only history
- Real carry-forward chains across meetings
- 10 knowledge base documents (runbooks, ADRs, policies, postmortems)
- Deliberate edge cases: unassigned items, missing due dates, owner no-show to source meeting
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.base import Base
from app.db.models import (
    ActionItem,
    Availability,
    ItemEventType,
    ItemHistory,
    ItemStatus,
    KBDocument,
    KBLink,
    Meeting,
    MeetingStatus,
    MeetingType,
    Participant,
    Person,
    Priority,
    RSVP,
    ResolutionType,
)
from app.db.session import engine, SessionLocal


def seed():
    """
    Seed the database with realistic demo data.
    Idempotent: safe to call multiple times. Clears and re-seeds when data exists.
    """
    print("[*] Initializing ContextKeeper seed...")
    # Ensure tables exist (idempotent — won't overwrite schema)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if already seeded
        if db.query(Person).count() > 0:
            print("[*] Existing data found — clearing for clean re-seed...")
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())
            db.commit()
        else:
            print("[*] Empty database — seeding fresh data...")

        now = datetime.now(timezone.utc)

        # ── 1. People ────────────────────────────────────────────────────────
        print("[*] Creating 6 teammates with realistic profiles & availability...")
        sarah = Person(
            name="Sarah Chen",
            email="sarah.chen@acme.corp",
            role="Staff Backend Engineer & Tech Lead",
            availability=Availability.available,
        )
        alex = Person(
            name="Alex Rodriguez",
            email="alex.rodriguez@acme.corp",
            role="Senior DevOps & Infrastructure Engineer",
            availability=Availability.on_leave,
            leave_start=now - timedelta(days=2),
            leave_end=now + timedelta(days=8),
        )
        priya = Person(
            name="Priya Patel",
            email="priya.patel@acme.corp",
            role="Product Manager",
            availability=Availability.available,
        )
        marcus = Person(
            name="Marcus Vance",
            email="marcus.vance@acme.corp",
            role="Frontend Architect",
            availability=Availability.available,
        )
        elena = Person(
            name="Elena Rostova",
            email="elena.rostova@acme.corp",
            role="Security & Compliance Engineer",
            availability=Availability.available,
        )
        david = Person(
            name="David Kim",
            email="david.kim@acme.corp",
            role="Data & Analytics Engineer",
            availability=Availability.available,
        )
        db.add_all([sarah, alex, priya, marcus, elena, david])
        db.flush()

        # ── 2. Knowledge Base Documents ──────────────────────────────────────
        print("Ingesting 10 Knowledge Base documents (Runbooks, ADRs, Postmortems)...")
        kb_docs = [
            KBDocument(
                title="ADR 004: SQLite WAL Mode for Local Dev and Multi-Process Safety",
                content=(
                    "Status: Accepted\nContext: Developers experienced intermittent 'database locked' errors "
                    "when running concurrent background tasks alongside web requests.\n"
                    "Decision: Enable SQLite Write-Ahead Logging (PRAGMA journal_mode=WAL) and enforce foreign key constraints.\n"
                    "Consequences: Dramatic concurrency throughput improvement for read queries; persistent shm/wal files created."
                ),
                doc_type="adr",
                tags="database, sqlite, concurrency, adr",
            ),
            KBDocument(
                title="Postgres Staging Migration Runbook",
                content=(
                    "1. Connect to AWS RDS bastion.\n2. Run `alembic upgrade head` with target DATABASE_URL.\n"
                    "3. Verify index creation: `SELECT indexname FROM pg_indexes WHERE tablename='action_items';`\n"
                    "4. If migration hangs, check pg_stat_activity for lingering open locks."
                ),
                doc_type="runbook",
                tags="postgres, migration, staging, runbook",
            ),
            KBDocument(
                title="ADR 007: API Versioning Scheme and Deprecation Policy",
                content=(
                    "Status: Accepted\nDecision: All REST endpoints will strictly follow URI versioning `/api/v1/...`.\n"
                    "Breaking changes require a 6-week sunset notice header `Sunset: <date>` and email to partners."
                ),
                doc_type="adr",
                tags="api, architecture, versioning, adr",
            ),
            KBDocument(
                title="On-Call Incident Escalation & Handoff Policy",
                content=(
                    "When rotating on-call on Mondays at 10:00 AM UTC, incoming engineer must review all unclosed P1/P2 items.\n"
                    "Outgoing primary must complete a 15-minute sync or provide an asynchronous Handover document in ContextKeeper."
                ),
                doc_type="policy",
                tags="on-call, incident, handoff, policy",
            ),
            KBDocument(
                title="Postmortem: 2026-10-14 Intermittent 504 Gateway Timeouts in Staging",
                content=(
                    "Impact: Staging API experienced 12 minutes of 504 responses.\n"
                    "Root Cause: Connection pool exhaustion during heavy transcript embedding calls.\n"
                    "Action Items: Added timeout circuit breaker and configured exponential backoff retries in AI runner."
                ),
                doc_type="postmortem",
                tags="postmortem, reliability, timeouts, ai",
            ),
            KBDocument(
                title="OAuth2 & API Key Security Guidelines",
                content=(
                    "Never store plain API keys in code or persistent logs. All AI provider tokens must be loaded via "
                    "environment variables. Redaction filters must mask patterns matching tokens or keys before logging."
                ),
                doc_type="policy",
                tags="security, api-key, redaction, policy",
            ),
            KBDocument(
                title="Engineer Onboarding & Context Catch-Up Guide",
                content=(
                    "Welcome to engineering! To quickly get up to speed on active projects, use the ContextKeeper "
                    "Catch-Up Brief tool to review meetings from the last 2 weeks tailored to your domain."
                ),
                doc_type="onboarding",
                tags="onboarding, documentation",
            ),
            KBDocument(
                title="Frontend Performance & Bundle Budget Policy",
                content=(
                    "Target maximum bundle transfer size of 150KB for initial dashboard load.\n"
                    "Prefer server-rendered markup with Alpine.js reactivity and Tailwind CSS."
                ),
                doc_type="policy",
                tags="frontend, performance, tailwind",
            ),
            KBDocument(
                title="ADR 009: Background Automation & Task Scheduling",
                content=(
                    "Status: Accepted\nDecision: Avoid distributed Celery queues for standard lightweight polling.\n"
                    "Rely on asynchronous FastAPI background tasks and standard SQLite WAL concurrency."
                ),
                doc_type="adr",
                tags="backend, async, tasks",
            ),
            KBDocument(
                title="Production Release Checklist & Rollback Procedures",
                content=(
                    "Pre-flight:\n- Check CI tests passing on main\n- Verify database migration compatibility\n"
                    "Rollback command: `alembic downgrade -1`\nNotify #eng-releases Slack channel immediately."
                ),
                doc_type="runbook",
                tags="release, deploy, runbook",
            ),
        ]
        db.add_all(kb_docs)
        db.flush()

        # ── 3. Meetings & Handovers across 3 weeks ────────────────────────────
        print("Creating 6 meetings and 2 handovers spanning 3 weeks...")

        # Meeting 1 (3 weeks ago) - Completed
        m1 = Meeting(
            title="Q4 Sprint 21 Planning & Architecture Alignment",
            meeting_type=MeetingType.meeting,
            status=MeetingStatus.completed,
            scheduled_at=now - timedelta(days=21),
            agenda="- Review Q4 Roadmap deliverables\n- Discuss SQLite WAL vs Postgres migration timeline\n- Action assignments",
            raw_notes=(
                "Sarah: Welcome everyone. We need to agree on our database architecture before we scale the task service.\n"
                "Alex: SQLite is locking up under concurrent load. We should enable WAL mode immediately as a hotfix.\n"
                "Sarah: Agreed. Let's make an ADR for that.\n"
                "Priya: What about the staging Postgres instance?\n"
                "Alex: I can provision AWS RDS Postgres by next Wednesday.\n"
                "Marcus: Frontend needs the OpenAPI schemas updated as soon as the endpoints are locked."
            ),
            summary="Agreed to adopt SQLite WAL mode immediately for local development while Alex provisions RDS Postgres for staging.",
            decisions="- Adopted SQLite WAL mode for local dev\n- Scheduled Postgres staging migration for Sprint 22",
            ai_generated=True,
            version=2,
        )

        # Meeting 2 (2 weeks ago) - Completed
        m2 = Meeting(
            title="Sprint 22 Mid-Cycle Sync & Blocker Triage",
            meeting_type=MeetingType.meeting,
            status=MeetingStatus.completed,
            scheduled_at=now - timedelta(days=14),
            agenda="- Check Postgres migration status\n- Review frontend bundle size\n- Security review of AI keys",
            raw_notes=(
                "[10:02] Priya: Alex, how is the Postgres staging setup going?\n"
                "[10:04] Alex: RDS is spun up but I haven't completed the Alembic migrations yet.\n"
                "[10:06] Elena: Please make sure we don't log any OpenAI or Gemini API keys in the app logs.\n"
                "[10:08] Sarah: I will write a regex redaction processor for structlog today."
            ),
            summary="Reviewed infrastructure progress. Alex reported delay in staging migration. Sarah committed to logging redaction filter.",
            decisions="- Enforced strict key redaction in structured logging",
            ai_generated=True,
            version=3,
        )

        # Meeting 3 (1 week ago) - Handover before Alex's leave
        m3 = Meeting(
            title="DevOps & Infrastructure Handover (Alex -> Sarah)",
            meeting_type=MeetingType.handover,
            status=MeetingStatus.completed,
            scheduled_at=now - timedelta(days=7),
            agenda="- Hand over active AWS tasks before Alex's 10-day leave\n- Hand over Postgres migration runbook\n- On-call rotation cover",
            raw_notes=(
                "Slack Chat Dump:\n"
                "Alex: Hey Sarah, since I'm going on medical leave starting Thursday, here's where things stand.\n"
                "Alex: The RDS instance is active at staging-db.internal. The root secret is in Secrets Manager.\n"
                "Alex: The migration script needs someone to run `alembic upgrade head` and verify table constraints.\n"
                "Sarah: Got it. I'll take over the staging migration and cover on-call duties while you're away."
            ),
            summary="Alex handed over AWS staging infrastructure and migration responsibilities to Sarah during his upcoming leave.",
            decisions="- Sarah to cover DevOps escalation and finish staging Postgres rollout during Alex's leave",
            ai_generated=True,
            version=2,
        )

        # Meeting 4 (4 days ago) - In Progress
        m4 = Meeting(
            title="Sprint 23 Retrospective & Risk Review",
            meeting_type=MeetingType.meeting,
            status=MeetingStatus.completed,
            scheduled_at=now - timedelta(days=4),
            agenda="- Review carried over items from Sprint 22\n- Identify blocked tasks\n- Evaluate context-loss risks",
            raw_notes=(
                "Transcript: Sarah: Looking at our board, Alex's staging task has been carried forward twice already.\n"
                "Elena: We also have unassigned items from the security audit that need owners.\n"
                "Marcus: Frontend dashboard is ready to consume the /api/risk endpoints."
            ),
            summary="Identified carry-forward accumulation and unassigned security items.",
            decisions="- Prioritize clearing carried-forward infrastructure tasks",
            ai_generated=True,
            version=1,
        )

        # Meeting 5 (Yesterday) - In Progress
        m5 = Meeting(
            title="Urgent: Staging Database Migration Sync",
            meeting_type=MeetingType.meeting,
            status=MeetingStatus.in_progress,
            scheduled_at=now - timedelta(days=1),
            agenda="- Finalize Alembic scripts for Postgres\n- Verify foreign key constraints\n- Test rollback path",
            raw_notes="Meeting ongoing. Sarah executing migration runbook. Verifying index performance.",
            version=1,
        )

        # Meeting 6 (Tomorrow) - Scheduled
        m6 = Meeting(
            title="Sprint 24 Kickoff & Release Roadmap",
            meeting_type=MeetingType.meeting,
            status=MeetingStatus.scheduled,
            scheduled_at=now + timedelta(days=1),
            agenda="Agenda to be populated via Agenda Autopilot from carried-forward open items.",
            version=1,
        )

        # Meeting 7 (Next Week) - Scheduled Handover
        m7 = Meeting(
            title="Post-Leave Re-entry & Context Catch-Up (Alex return)",
            meeting_type=MeetingType.handover,
            status=MeetingStatus.scheduled,
            scheduled_at=now + timedelta(days=8),
            agenda="- Catch up Alex on changes made during leave\n- Re-handover DevOps responsibilities",
            version=1,
        )

        # Meeting 8 (Draft)
        m8 = Meeting(
            title="Future Architecture: Distributed Caching & Redis",
            meeting_type=MeetingType.meeting,
            status=MeetingStatus.draft,
            scheduled_at=now + timedelta(days=15),
            agenda="Draft proposal on redis caching layer.",
            version=1,
        )

        db.add_all([m1, m2, m3, m4, m5, m6, m7, m8])
        db.flush()

        # ── 4. Participants & RSVP ───────────────────────────────────────────
        print("Registering meeting participants and attendance records...")
        participants = [
            # Meeting 1
            Participant(meeting_id=m1.id, person_id=sarah.id, rsvp=RSVP.attended),
            Participant(meeting_id=m1.id, person_id=alex.id, rsvp=RSVP.attended),
            Participant(meeting_id=m1.id, person_id=priya.id, rsvp=RSVP.attended),
            Participant(meeting_id=m1.id, person_id=marcus.id, rsvp=RSVP.attended),
            # Meeting 2 (Alex no response - Deliberate edge case!)
            Participant(meeting_id=m2.id, person_id=sarah.id, rsvp=RSVP.attended),
            Participant(meeting_id=m2.id, person_id=alex.id, rsvp=RSVP.no_response),
            Participant(meeting_id=m2.id, person_id=priya.id, rsvp=RSVP.attended),
            Participant(meeting_id=m2.id, person_id=elena.id, rsvp=RSVP.attended),
            # Meeting 3
            Participant(meeting_id=m3.id, person_id=sarah.id, rsvp=RSVP.attended),
            Participant(meeting_id=m3.id, person_id=alex.id, rsvp=RSVP.attended),
            # Meeting 4
            Participant(meeting_id=m4.id, person_id=sarah.id, rsvp=RSVP.attended),
            Participant(meeting_id=m4.id, person_id=priya.id, rsvp=RSVP.attended),
            Participant(meeting_id=m4.id, person_id=marcus.id, rsvp=RSVP.attended),
            Participant(meeting_id=m4.id, person_id=alex.id, rsvp=RSVP.absent),  # On leave
            # Meeting 5
            Participant(meeting_id=m5.id, person_id=sarah.id, rsvp=RSVP.attended),
            Participant(meeting_id=m5.id, person_id=david.id, rsvp=RSVP.attended),
            # Meeting 6
            Participant(meeting_id=m6.id, person_id=sarah.id, rsvp=RSVP.accepted),
            Participant(meeting_id=m6.id, person_id=priya.id, rsvp=RSVP.accepted),
            Participant(meeting_id=m6.id, person_id=marcus.id, rsvp=RSVP.invited),
        ]
        db.add_all(participants)
        db.flush()

        # ── 5. Action Items & Full History Trail (~25 items) ───────────────────
        print("Generating ~25 realistic action items with full event history and carry-forwards...")

        # Item 1: High Risk Overdue (Alex on leave, carried forward 3 times!)
        item1 = ActionItem(
            title="Execute Postgres staging migration script and verify foreign keys",
            description="Run alembic upgrade head against staging RDS instance and test foreign key constraints.",
            owner_id=alex.id,  # Owner is on leave!
            due_date=now - timedelta(days=3),  # Overdue!
            status=ItemStatus.open,
            priority=Priority.critical,
            source_meeting_id=m1.id,
            current_meeting_id=m4.id,
            carry_forward_count=3,  # Carried forward 3 times!
            confidence=0.95,
            source_quote="I can provision AWS RDS Postgres by next Wednesday",
            ai_generated=True,
        )
        db.add(item1)
        db.flush()

        _add_history(db, item1.id, ItemEventType.created, sarah.id, "", item1.title, "Created from Meeting 1 recap")
        _add_history(db, item1.id, ItemEventType.carried_forward, priya.id, str(m1.id), str(m2.id), "Carried forward to Sprint 22")
        _add_history(db, item1.id, ItemEventType.carried_forward, priya.id, str(m2.id), str(m4.id), "Carried forward to Sprint 23 (Overdue)")

        # Item 2: Unassigned Edge Case (High Risk: no owner)
        item2 = ActionItem(
            title="Configure connection pool circuit breaker for AI API timeouts",
            description="Prevent 504 timeouts seen in postmortem by wrapping provider calls in circuit breaker.",
            owner_id=None,  # Unassigned!
            due_date=now + timedelta(days=2),
            status=ItemStatus.open,
            priority=Priority.high,
            source_meeting_id=m2.id,
            current_meeting_id=m4.id,
            carry_forward_count=1,
            confidence=0.9,
            source_quote="Added timeout circuit breaker and configured exponential backoff",
            ai_generated=True,
        )
        db.add(item2)
        db.flush()
        _add_history(db, item2.id, ItemEventType.created, sarah.id, "", item2.title, "Extracted from postmortem")

        # Item 3: Closed item with mandatory outcome recorded
        item3 = ActionItem(
            title="Implement structlog regex redaction filter for API keys & tokens",
            description="Redact any string matching API key or Bearer token patterns from console and file logs.",
            owner_id=sarah.id,
            due_date=now - timedelta(days=5),
            status=ItemStatus.done,
            priority=Priority.high,
            source_meeting_id=m2.id,
            current_meeting_id=m2.id,
            outcome="Implemented _redact_processor in logging_config.py with regex tests passing 100%.",
            resolution_type=ResolutionType.completed,
            closed_at=now - timedelta(days=5),
            confidence=1.0,
            ai_generated=False,
        )
        db.add(item3)
        db.flush()
        _add_history(db, item3.id, ItemEventType.created, sarah.id, "", item3.title, "Created in Sprint 22")
        _add_history(db, item3.id, ItemEventType.outcome_recorded, sarah.id, "", item3.outcome, "Closed with outcome")

        # Item 4: Blocked Item (High Risk)
        item4 = ActionItem(
            title="Deploy OpenAPI v1 route gateway in production reverse proxy",
            description="Configure NGINX routing for /api/v1/ prefix according to ADR 007.",
            owner_id=marcus.id,
            due_date=now - timedelta(days=1),
            status=ItemStatus.blocked,  # Blocked!
            priority=Priority.high,
            source_meeting_id=m2.id,
            current_meeting_id=m4.id,
            carry_forward_count=2,
            confidence=0.88,
            source_quote="API will be versioned at /api/v1/ going forward",
            ai_generated=True,
        )
        db.add(item4)
        db.flush()
        _add_history(db, item4.id, ItemEventType.created, marcus.id, "", item4.title, "Created")
        _add_history(db, item4.id, ItemEventType.status_changed, marcus.id, "in_progress", "blocked", "Waiting on staging migration")

        # Item 5: Reassigned with No Handover Note (Risk Signal!)
        item5 = ActionItem(
            title="Review security posture of environment variable injection",
            description="Audit Dockerfile and compose configs to ensure secrets aren't baked into image layers.",
            owner_id=elena.id,
            due_date=now + timedelta(days=4),
            status=ItemStatus.in_progress,
            priority=Priority.medium,
            source_meeting_id=m3.id,
            current_meeting_id=m4.id,
            confidence=0.92,
            ai_generated=True,
        )
        db.add(item5)
        db.flush()
        _add_history(db, item5.id, ItemEventType.created, alex.id, "", item5.title, "Created")
        _add_history(db, item5.id, ItemEventType.reassigned, sarah.id, str(alex.id), str(elena.id), "")  # Empty note!

        # Items 6-25 (Diverse realistic tasks)
        more_items = [
            ("Write unit tests for lifecycle state machine transitions", sarah.id, m1.id, m2.id, ItemStatus.done, Priority.medium, ResolutionType.completed, "Tests written in test_lifecycle.py"),
            ("Document SQLite WAL concurrency benchmark findings", sarah.id, m1.id, m1.id, ItemStatus.done, Priority.low, ResolutionType.completed, "Published to team wiki"),
            ("Set up Pydantic V2 schema validation for catch-up brief endpoint", david.id, m2.id, m4.id, ItemStatus.open, Priority.medium, None, ""),
            ("Verify X-Request-ID propagation in error responses", sarah.id, m2.id, m5.id, ItemStatus.in_progress, Priority.high, None, ""),
            ("Conduct benchmark on TF-IDF vs embedding retrieval latency", david.id, m3.id, m4.id, ItemStatus.open, Priority.medium, None, ""),
            ("Verify Docker multi-stage build cache in CI runner", alex.id, m1.id, m4.id, ItemStatus.open, Priority.low, None, ""),  # Alex on leave!
            ("Implement close dialog modal requiring non-empty outcome", marcus.id, m4.id, m4.id, ItemStatus.in_progress, Priority.high, None, ""),
            ("Create mock AI provider with configurable failure injection", sarah.id, m2.id, m2.id, ItemStatus.done, Priority.critical, ResolutionType.completed, "Mock provider supporting MOCK_AI_FAIL created"),
            ("Add rate limiter middleware to AI generation endpoints", elena.id, m3.id, m4.id, ItemStatus.open, Priority.medium, None, ""),
            ("Audit CSS typography contrast for accessibility compliance", marcus.id, m4.id, m4.id, ItemStatus.open, Priority.low, None, ""),
            ("Extract action items from messy email thread test fixture", priya.id, m4.id, m4.id, ItemStatus.done, Priority.medium, ResolutionType.completed, "Added to seed fixtures"),
            ("Draft weekly engineering update for leadership", priya.id, m4.id, m6.id, ItemStatus.open, Priority.medium, None, ""),
            ("Verify foreign key cascade deletions on test database", sarah.id, m1.id, m1.id, ItemStatus.done, Priority.medium, ResolutionType.completed, "FK cascade verified"),
            ("Review PR #42: Handover Risk Radar mathematical weighting", sarah.id, m4.id, m5.id, ItemStatus.in_progress, Priority.critical, None, ""),
            ("Verify SQLite FTS5 extension availability in Docker image", alex.id, m2.id, m4.id, ItemStatus.open, Priority.medium, None, ""),  # Alex on leave!
            ("Document prompt-injection defense delimiters in README", elena.id, m3.id, m4.id, ItemStatus.open, Priority.high, None, ""),
            ("Test optimistic concurrency lock rejection on item edit", sarah.id, m3.id, m3.id, ItemStatus.done, Priority.high, ResolutionType.completed, "Conflict 409 tested successfully"),
            ("Build copy-to-clipboard functionality for AI smart nudges", marcus.id, m4.id, m4.id, ItemStatus.done, Priority.medium, ResolutionType.completed, "Built with Navigator clipboard API"),
            ("Set up health check probe endpoint at /healthz", sarah.id, m1.id, m1.id, ItemStatus.done, Priority.low, ResolutionType.completed, "Endpoint active"),
            ("Validate idempotency key deduplication on recap commit", sarah.id, m4.id, m5.id, ItemStatus.in_progress, Priority.critical, None, ""),
        ]

        for title, owner_id, src_m, cur_m, status, priority, res_type, outcome in more_items:
            due = now + timedelta(days=2) if status != ItemStatus.done else now - timedelta(days=4)
            item = ActionItem(
                title=title,
                owner_id=owner_id,
                due_date=due,
                status=status,
                priority=priority,
                source_meeting_id=src_m,
                current_meeting_id=cur_m,
                outcome=outcome,
                resolution_type=res_type,
                closed_at=now - timedelta(days=2) if status == ItemStatus.done else None,
                ai_generated=True,
            )
            db.add(item)
            db.flush()
            _add_history(db, item.id, ItemEventType.created, sarah.id, "", item.title, "Created")
            if status == ItemStatus.done:
                _add_history(db, item.id, ItemEventType.outcome_recorded, sarah.id, "", outcome, "Item closed")

        # ── 6. KB Links ──────────────────────────────────────────────────────
        print("Linking meetings & action items to Knowledge Base runbooks...")
        kb_links = [
            KBLink(meeting_id=m1.id, kb_doc_id=kb_docs[0].id, relevance_score=0.95, reason="ADR 004 directly created in this session", accepted=True),
            KBLink(meeting_id=m1.id, kb_doc_id=kb_docs[1].id, relevance_score=0.88, reason="Postgres staging runbook covers discussed migration", accepted=True),
            KBLink(meeting_id=m2.id, kb_doc_id=kb_docs[2].id, relevance_score=0.91, reason="API versioning ADR defines topic discussed", accepted=True),
            KBLink(meeting_id=m3.id, kb_doc_id=kb_docs[3].id, relevance_score=0.94, reason="On-call escalation policy guides this handover", accepted=True),
            KBLink(item_id=item1.id, kb_doc_id=kb_docs[1].id, relevance_score=0.98, reason="Step-by-step procedure for executing migration", accepted=True),
        ]
        db.add_all(kb_links)

        db.commit()
        print("[SUCCESS] ContextKeeper database successfully seeded!")
        print("   - 6 People (1 on leave: Alex Rodriguez)")
        print("   - 8 Sessions (Meetings & Handovers)")
        print("   - 25 Action items with complete event history")
        print("   - 10 Knowledge base runbooks and ADRs")

    finally:
        db.close()


def _add_history(db, item_id, event_type, actor_id, old_val, new_val, note):
    h = ItemHistory(
        item_id=item_id,
        event_type=event_type,
        actor_id=actor_id,
        old_value=old_val,
        new_value=new_val,
        note=note,
        timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.add(h)


if __name__ == "__main__":
    seed()
