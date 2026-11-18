"""Sync bookkeeping for external connectors.

Two tables, two jobs:

* ``ConnectorSyncState`` — one row per connector, holding the incremental
  sync cursor (``last_synced_at`` / ``last_external_id``). The row is
  locked with ``SELECT ... FOR UPDATE`` when the cursor is advanced, so
  two transactions cannot advance it to different values.
* ``ConnectorSyncRun`` — one row per sync attempt, including runs that
  were refused because another run was active. The ``active_key`` column
  is the lease: it is set to the connector name while a run is in
  progress and cleared (NULL) when the run finishes. It is UNIQUE and
  NULLable, so MySQL and SQLite both allow many finished runs (NULL)
  but at most one live run per connector. A second starter that hits
  the unique constraint gets an ``already_running`` run instead of
  writing data — that is the "one clean winner" rule, enforced by the
  database, not by an in-process flag.
"""

from django.db import models


class ConnectorSyncState(models.Model):
    connector_name = models.CharField(max_length=80, unique=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_external_id = models.CharField(max_length=80, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.connector_name} @ {self.last_synced_at or 'never'}"


class ConnectorSyncRun(models.Model):
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_ALREADY_RUNNING = "already_running"
    STATUS_CHOICES = [
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
        (STATUS_ALREADY_RUNNING, "Already running"),
    ]

    connector_name = models.CharField(max_length=80, db_index=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING
    )
    # Lease: connector name while live, NULL once finished. Unique, so
    # at most one live run per connector can exist in the database.
    active_key = models.CharField(
        max_length=80, unique=True, null=True, blank=True
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    records_fetched = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    records_updated = models.PositiveIntegerField(default=0)
    records_skipped = models.PositiveIntegerField(default=0)
    mapping_errors = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, default="")
    # Free-form detail: mapping-error samples (capped), customer
    # creations, cursor before/after. Never contains secrets.
    details = models.JSONField(default=dict)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.connector_name} #{self.pk} {self.status}"
