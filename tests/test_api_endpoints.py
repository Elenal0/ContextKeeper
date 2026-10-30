"""Tests for FastAPI endpoints, request-ID propagation, and recap idempotency."""
import uuid
import pytest


def test_healthz_endpoint(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database" in data
    assert "ai_provider" in data


def test_request_id_propagation_in_header(client):
    req_id = str(uuid.uuid4())
    response = client.get("/healthz", headers={"X-Request-ID": req_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == req_id


def test_recap_commit_idempotency(client, db_session):
    # 1. Create a meeting
    m_res = client.post("/api/meetings", json={"title": "Planning Meeting"})
    assert m_res.status_code == 201
    meeting_id = m_res.json()["id"]

    idempotency_key = f"idem-key-{uuid.uuid4()}"
    draft_payload = {
        "summary": "Agreed on staging DB.",
        "decisions": ["Use Postgres on RDS"],
        "action_items": [
            {
                "title": "Migrate schema to staging",
                "description": "Run alembic upgrade head",
                "owner": "Sarah",
                "priority": "high",
                "confidence": 0.95,
                "source_quote": "run alembic upgrade",
            }
        ],
        "open_questions": [],
        "risks": [],
    }

    # First commit
    commit_res1 = client.post(
        "/api/ai/recap/commit",
        json={
            "meeting_id": meeting_id,
            "draft": draft_payload,
            "idempotency_key": idempotency_key,
        },
    )
    assert commit_res1.status_code == 200
    assert commit_res1.json()["status"] == "success"
    assert len(commit_res1.json()["items_created"]) == 1

    # Second commit with SAME idempotency key (Double click simulation)
    commit_res2 = client.post(
        "/api/ai/recap/commit",
        json={
            "meeting_id": meeting_id,
            "draft": draft_payload,
            "idempotency_key": idempotency_key,
        },
    )
    assert commit_res2.status_code == 200
    # Must report already_committed and NOT duplicate action items
    assert commit_res2.json()["status"] == "already_committed"

    # Verify action items count in database for this meeting is still exactly 1
    items_res = client.get(f"/api/items?meeting_id={meeting_id}")
    assert len(items_res.json()) == 1


def test_error_envelope_format_on_validation_failure(client):
    # Missing required title in meeting create
    response = client.post("/api/meetings", json={})
    assert response.status_code == 422
    err_body = response.json()
    assert "error" in err_body
    assert err_body["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in err_body["error"]
    assert "request_id" in err_body["error"]
    assert response.headers.get("X-Request-ID") != ""

