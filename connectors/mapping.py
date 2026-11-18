"""External -> ReconDesk mapping. One module, no database access.

Every function here is pure: raw dict in, plain dict out (or
:class:`MappingError`). The sync service resolves customers and
writes rows; mapping never touches the database, so it is unit
testable with no Django setup beyond ``core.logic.money``.

A record that fails mapping is *not* a sync failure: the caller logs
the error (record id, field, reason) and continues with the next
record. Amounts reuse ``core.logic.money`` so external amounts get
exactly the same validation as ReconDesk's own money (positive,
at most two decimals).
"""

from datetime import date, datetime, timezone

from core.logic import money

from .errors import MappingError


def _require(raw, field):
    value = raw.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise MappingError(raw.get("id"), field, "missing or empty")
    return value


def _text(raw, field, *, required=True):
    value = raw.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise MappingError(raw.get("id"), field, "missing or empty")
        return ""
    return str(value).strip()


def _parse_date(raw, field):
    value = _require(raw, field)
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise MappingError(raw.get("id"), field, f"not a date: {text!r}") from exc


def _parse_datetime(raw, field):
    value = raw.get(field)
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise MappingError(
                raw.get("id"), field, f"not a datetime: {text!r}"
            ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_amount(raw, field="amount"):
    value = _require(raw, field)
    try:
        return money(value)
    except ValueError as exc:
        raise MappingError(raw.get("id"), field, str(exc)) from exc


def _customer(raw):
    name = _text(raw, "customer_name", required=False)
    email = _text(raw, "customer_email", required=False)
    if not name and not email:
        raise MappingError(raw.get("id"), "customer", "no name or email")
    if email and "@" not in email:
        raise MappingError(raw.get("id"), "customer_email", f"not an email: {email!r}")
    return name, email


def map_invoice(raw):
    """Map one external invoice record to ReconDesk Invoice fields."""
    if not isinstance(raw, dict):
        raise MappingError(None, "record", "record is not an object")
    external_id = _text(raw, "id")
    name, email = _customer(raw)
    return {
        "external_id": external_id,
        "number": _text(raw, "number"),
        "customer_name": name,
        "customer_email": email,
        "issued_on": _parse_date(raw, "issued_on"),
        "due_on": _parse_date(raw, "due_on"),
        "amount": _parse_amount(raw),
        "updated_at": _parse_datetime(raw, "updated_at"),
    }


def map_payment(raw):
    """Map one external payment record to ReconDesk Payment fields."""
    if not isinstance(raw, dict):
        raise MappingError(None, "record", "record is not an object")
    external_id = _text(raw, "id")
    name, email = _customer(raw)
    return {
        "external_id": external_id,
        "reference": _text(raw, "reference"),
        "invoice_hint": _text(raw, "invoice_number", required=False),
        "customer_name": name,
        "customer_email": email,
        "paid_on": _parse_date(raw, "paid_on"),
        "amount": _parse_amount(raw),
        "updated_at": _parse_datetime(raw, "updated_at"),
    }
