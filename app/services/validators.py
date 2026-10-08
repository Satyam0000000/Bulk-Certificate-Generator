"""Per-recipient validation as pure functions (easy to unit-test).

Rule: one bad row fails only that row, never the whole request.
Duplicates are checked within a single job only (case-insensitive email).
"""
from email_validator import EmailNotValidError, validate_email

MAX_NAME_LEN = 100


def validate_recipient(raw, seen_emails: set[str]) -> tuple[str, str | None, str | None]:
    """Return (name, email, error). error is None when the row is valid."""
    if not isinstance(raw, dict):
        return "", None, "name is required"

    name_raw = raw.get("name")
    if name_raw is None:
        return "", None, "name is required"
    if not isinstance(name_raw, str):
        return "", None, "name must be a string"

    name = name_raw.strip()
    if not name:
        return "", None, "name must not be empty"
    if len(name) > MAX_NAME_LEN:
        return name[:MAX_NAME_LEN], None, f"name is too long (max {MAX_NAME_LEN} characters)"
    if any(ord(ch) < 32 for ch in name):
        return name, None, "name contains invalid characters"

    email_raw = raw.get("email")
    if email_raw is None or (isinstance(email_raw, str) and email_raw.strip() == ""):
        return name, None, None
    if not isinstance(email_raw, str):
        return name, None, "invalid email format"

    email = email_raw.strip()
    try:
        info = validate_email(email, check_deliverability=False)
        email = info.normalized
    except EmailNotValidError:
        return name, email, "invalid email format"

    key = email.lower()
    if key in seen_emails:
        return name, email, "duplicate recipient"
    seen_emails.add(key)
    return name, email, None
