"""Staff-only API for connector syncs.

A sync triggered here runs synchronously in the request (the mock
sync of a few hundred records takes well under a second). A
production deployment would queue this instead; see docs/CONNECTORS.md.
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .config import ConnectorConfig
from .errors import ConnectorError
from .mock_connector import MockConnector
from .models import ConnectorSyncRun


def _run_payload(run):
    return {
        "run_id": run.pk,
        "connector": run.connector_name,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "records_fetched": run.records_fetched,
        "records_created": run.records_created,
        "records_updated": run.records_updated,
        "records_skipped": run.records_skipped,
        "mapping_errors": run.mapping_errors,
        "error": run.error,
    }


@api_view(["POST"])
def trigger_sync(request):
    if not request.user.is_staff:
        return Response({"error": "Staff only"}, status=403)
    connector = MockConnector(config=ConnectorConfig.from_env())
    try:
        run = connector.sync(full=bool(request.data.get("full", False)))
    except ConnectorError as exc:
        return Response({"error": str(exc)}, status=503)
    if run.status == ConnectorSyncRun.STATUS_ALREADY_RUNNING:
        return Response(_run_payload(run), status=200)
    if run.status == ConnectorSyncRun.STATUS_FAILED:
        return Response(_run_payload(run), status=503)
    return Response(_run_payload(run), status=201)


@api_view(["GET"])
def sync_runs(request):
    runs = ConnectorSyncRun.objects.all().order_by("-started_at")[:20]
    return Response([_run_payload(run) for run in runs])
