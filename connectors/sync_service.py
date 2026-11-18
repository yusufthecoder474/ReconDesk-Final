"""Sync orchestration: leasing, customer resolution, upserts, cursor.

This is the only module that writes ReconDesk rows for a sync. The
connector itself only fetches and maps; this service decides what
lands in the database, so the concurrency and idempotency rules are
in one place and every connector inherits them.

Customer resolution (approved default): match by email first, then
by name; otherwise create the customer from the external name/email
and count the creation in the run details. No customer is ever
created silently without that count.
"""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import Customer, Invoice, Payment, PaymentAllocation

from .errors import MappingError
from .models import ConnectorSyncRun, ConnectorSyncState

MAX_MAPPING_ERROR_SAMPLES = 50
BATCH_SIZE = 500

_MODEL = {"invoices": Invoice, "payments": Payment}
_UPDATE_FIELDS = {
    "invoices": ["customer", "number", "issued_on", "due_on", "amount"],
    "payments": ["customer", "reference", "invoice_hint", "paid_on", "amount"],
}


# -- leasing ----------------------------------------------------------


def acquire_run(connector_name):
    """Try to start a run. Returns ``(run, is_winner)``.

    The winner holds the lease (``active_key=connector_name`` on its
    run row). A loser gets an ``already_running`` run row and writes
    nothing. The lease is a unique database constraint, so this holds
    across processes — not just threads in one process.
    """
    try:
        with transaction.atomic():
            ConnectorSyncState.objects.select_for_update().get_or_create(
                connector_name=connector_name
            )
            run = ConnectorSyncRun.objects.create(
                connector_name=connector_name,
                active_key=connector_name,
                status=ConnectorSyncRun.STATUS_RUNNING,
            )
        return run, True
    except IntegrityError:
        run = ConnectorSyncRun.objects.create(
            connector_name=connector_name,
            status=ConnectorSyncRun.STATUS_ALREADY_RUNNING,
            finished_at=timezone.now(),
            details={"reason": "another sync run is already active"},
        )
        return run, False


def finish_run(run, status, error="", details=None):
    run.status = status
    run.finished_at = timezone.now()
    run.active_key = None
    run.error = error or ""
    if details:
        merged = dict(run.details or {})
        merged.update(details)
        run.details = merged
    run.save(
        update_fields=[
            "status",
            "finished_at",
            "active_key",
            "error",
            "details",
            "records_fetched",
            "records_created",
            "records_updated",
            "records_skipped",
            "mapping_errors",
        ]
    )
    return run


def clear_stale_lease(connector_name, force=False, max_age_minutes=60):
    """Clear a lease left behind by a crashed run.

    ``force=True`` clears any live run (operator action, e.g. the
    ``--force`` flag). Otherwise only runs older than
    ``max_age_minutes`` are cleared. Returns the number cleared.
    """
    live = ConnectorSyncRun.objects.filter(
        connector_name=connector_name,
        status=ConnectorSyncRun.STATUS_RUNNING,
    )
    if not force:
        cutoff = timezone.now() - timedelta(minutes=max_age_minutes)
        live = live.filter(started_at__lt=cutoff)
    count = 0
    for run in live:
        finish_run(
            run,
            ConnectorSyncRun.STATUS_FAILED,
            error="Lease cleared: previous run did not finish",
        )
        count += 1
    return count


# -- customers --------------------------------------------------------


def resolve_customer(name, email):
    """Match by email, then name, else create. Returns (customer, created)."""
    if email:
        existing = Customer.objects.filter(email__iexact=email).first()
        if existing:
            return existing, False
    if name:
        existing = Customer.objects.filter(name__iexact=name).first()
        if existing:
            return existing, False
    customer = Customer.objects.create(name=name or email, email=email or "")
    return customer, True


# -- upserts ----------------------------------------------------------


def _fields_differ(obj, values):
    """True if any resolved field value differs from the stored row.

    ``values`` is the already-resolved dict (customer is a Customer
    instance, not the external name/email), so the comparison is
    apples-to-apples with the model fields.
    """
    for field, value in values.items():
        if field == "customer":
            if obj.customer_id != value.pk:
                return True
        elif getattr(obj, field) != value:
            return True
    return False


def _is_protected(resource, obj):
    """True if the row must not be changed by a sync.

    Finalized invoices and allocated payments are immutable in
    ReconDesk (``core.models`` enforces this in ``save()``); a sync
    that tried to change them would be a data-integrity bug, so the
    record is skipped and logged instead.
    """
    if resource == "invoices":
        return obj.finalized
    return PaymentAllocation.objects.filter(payment_id=obj.pk).exists()


def persist_batch(resource, mapped_records, *, source, use_bulk=True):
    """Upsert one page of mapped records. Returns a counts dict.

    Partition first (create / update / skip), then write in bulk.
    Skips are: unchanged rows, protected rows (finalized/allocated)
    whose external values differ, and invoice-number collisions with
    a different external id. Nothing here raises for a single bad
    row — the caller already filtered mapping errors.
    """
    model = _MODEL[resource]
    fields = _UPDATE_FIELDS[resource]
    counts = {"created": 0, "updated": 0, "skipped": 0}
    skipped_reasons = []

    external_ids = [m["external_id"] for m in mapped_records]
    existing = {
        obj.external_id: obj
        for obj in model.objects.filter(source=source, external_id__in=external_ids)
    }
    by_number = {}
    if resource == "invoices":
        numbers = [m["number"] for m in mapped_records]
        by_number = {
            obj.number: obj
            for obj in Invoice.objects.filter(number__in=numbers)
        }

    creates, updates = [], []
    for mapped in mapped_records:
        customer, created_customer = resolve_customer(
            mapped["customer_name"], mapped["customer_email"]
        )
        if created_customer:
            counts.setdefault("customers_created", 0)
            counts["customers_created"] += 1
        obj = existing.get(mapped["external_id"])
        values = {f: mapped[f] for f in fields if f != "customer"}
        values["customer"] = customer
        if obj is None:
            if resource == "invoices":
                clash = by_number.get(mapped["number"])
                if clash is not None:
                    counts["skipped"] += 1
                    skipped_reasons.append(
                        f"{mapped['external_id']}: number "
                        f"{mapped['number']} belongs to another invoice"
                    )
                    continue
            creates.append(model(source=source, external_id=mapped["external_id"], **values))
            continue
        if resource == "invoices":
            clash = by_number.get(mapped["number"])
            if clash is not None and clash.pk != obj.pk:
                counts["skipped"] += 1
                skipped_reasons.append(
                    f"{mapped['external_id']}: number "
                    f"{mapped['number']} belongs to another invoice"
                )
                continue
        if _is_protected(resource, obj):
            if _fields_differ(obj, values):
                counts["skipped"] += 1
                skipped_reasons.append(
                    f"{mapped['external_id']}: protected row "
                    "(finalized invoice / allocated payment) differs; not changed"
                )
            else:
                counts["skipped"] += 1
            continue
        if _fields_differ(obj, values):
            for field, value in values.items():
                setattr(obj, field, value)
            updates.append(obj)
        else:
            counts["skipped"] += 1

    if creates:
        if use_bulk:
            try:
                model.objects.bulk_create(creates, batch_size=BATCH_SIZE)
            except IntegrityError:
                # Defensive fallback (e.g. a concurrent writer outside
                # the lease): fall back to per-row upserts for this batch.
                for obj in creates:
                    model.objects.update_or_create(
                        source=source,
                        external_id=obj.external_id,
                        defaults={f: getattr(obj, f) for f in fields}
                        | {"customer": obj.customer},
                    )
        else:
            for obj in creates:
                obj.save()
        counts["created"] += len(creates)
    if updates:
        if use_bulk:
            model.objects.bulk_update(updates, fields, batch_size=BATCH_SIZE)
        else:
            for obj in updates:
                obj.save()
        counts["updated"] += len(updates)
    counts["skipped_reasons"] = skipped_reasons
    return counts


# -- orchestration ----------------------------------------------------


def run_sync(connector, full=False, use_bulk=True):
    """Drive one connector to exhaustion and return its SyncRun."""
    run, is_winner = acquire_run(connector.name)
    if not is_winner:
        return run
    mapping_errors = []
    customers_created = 0
    max_updated_at = None
    max_external_id = ""
    try:
        connector.authenticate()
        state = ConnectorSyncState.objects.filter(
            connector_name=connector.name
        ).first()
        updated_since = None
        if not full and state is not None:
            updated_since = state.last_synced_at
        for resource in connector.resources:
            cursor = None
            while True:
                page = connector.fetch_page(
                    resource, cursor=cursor, updated_since=updated_since
                )
                records = connector.extract(page)
                run.records_fetched += len(records)
                mapped_records = []
                for raw in records:
                    try:
                        mapped = connector.map_to_internal(resource, raw)
                    except MappingError as exc:
                        run.mapping_errors += 1
                        if len(mapping_errors) < MAX_MAPPING_ERROR_SAMPLES:
                            mapping_errors.append(
                                {
                                    "resource": resource,
                                    "record_id": exc.record_id,
                                    "field": exc.field,
                                    "reason": exc.reason,
                                }
                            )
                        continue
                    mapped_records.append(mapped)
                    updated_at = mapped.get("updated_at")
                    if updated_at is not None and (
                        max_updated_at is None
                        or (updated_at, mapped["external_id"])
                        > (max_updated_at, max_external_id)
                    ):
                        max_updated_at = updated_at
                        max_external_id = mapped["external_id"]
                if mapped_records:
                    counts = persist_batch(
                        resource,
                        mapped_records,
                        source=connector.name,
                        use_bulk=use_bulk,
                    )
                    run.records_created += counts["created"]
                    run.records_updated += counts["updated"]
                    run.records_skipped += counts["skipped"]
                    customers_created += counts.get("customers_created", 0)
                    if counts.get("skipped_reasons"):
                        details = dict(run.details or {})
                        reasons = details.setdefault("skipped_reasons", [])
                        reasons.extend(counts["skipped_reasons"][:20])
                        run.details = details
                if page.next_cursor is None:
                    break
                cursor = page.next_cursor
        if max_updated_at is not None:
            with transaction.atomic():
                state = (
                    ConnectorSyncState.objects.select_for_update()
                    .filter(connector_name=connector.name)
                    .first()
                )
                if state is None:
                    ConnectorSyncState.objects.create(
                        connector_name=connector.name,
                        last_synced_at=max_updated_at,
                        last_external_id=max_external_id,
                    )
                elif (
                    state.last_synced_at is None
                    or max_updated_at > state.last_synced_at
                ):
                    state.last_synced_at = max_updated_at
                    state.last_external_id = max_external_id
                    state.save(update_fields=["last_synced_at", "last_external_id"])
        finish_run(
            run,
            ConnectorSyncRun.STATUS_SUCCEEDED,
            details={
                "mapping_errors": mapping_errors,
                "customers_created": customers_created,
                "full": full,
                "use_bulk": use_bulk,
            },
        )
    except Exception as exc:  # noqa: BLE001 - run must be marked failed
        finish_run(
            run,
            ConnectorSyncRun.STATUS_FAILED,
            error=f"{type(exc).__name__}: {exc}",
            details={
                "mapping_errors": mapping_errors,
                "customers_created": customers_created,
                "full": full,
                "use_bulk": use_bulk,
            },
        )
        raise
    return run
