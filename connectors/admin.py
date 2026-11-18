"""Sync bookkeeping is read-only in admin; syncs run via the
management command or the staff API, never by editing rows here."""

from django.contrib import admin

from .models import ConnectorSyncRun, ConnectorSyncState


@admin.register(ConnectorSyncState)
class ConnectorSyncStateAdmin(admin.ModelAdmin):
    list_display = ("connector_name", "last_synced_at", "last_external_id")
    readonly_fields = ("connector_name", "last_synced_at", "last_external_id")


@admin.register(ConnectorSyncRun)
class ConnectorSyncRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "connector_name",
        "status",
        "started_at",
        "records_fetched",
        "records_created",
        "records_updated",
        "mapping_errors",
    )
    readonly_fields = (
        "connector_name",
        "status",
        "active_key",
        "started_at",
        "finished_at",
        "records_fetched",
        "records_created",
        "records_updated",
        "records_skipped",
        "mapping_errors",
        "error",
        "details",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
