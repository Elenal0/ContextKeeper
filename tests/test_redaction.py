"""Unit tests for logging redaction filter."""
from app.logging_config import redact


def test_redact_api_key_patterns():
    text = "Authorization failed with api_key=AIzaSyD-1234567890abcdef"
    redacted = redact(text)
    assert "AIzaSyD" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_token_and_secret():
    text = "secret: super_secret_pass_123 and token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    redacted = redact(text)
    assert "super_secret" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_emails():
    text = "Contact the engineer at dev.lead@company.internal for access."
    redacted = redact(text)
    assert "dev.lead@company.internal" not in redacted
    assert "[REDACTED]" in redacted


def test_preserve_non_sensitive_text():
    text = "Meeting summary: team decided to use SQLite WAL mode."
    redacted = redact(text)
    assert redacted == text

