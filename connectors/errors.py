"""Connector errors. Messages never contain secret values."""


class ConnectorError(Exception):
    """Base error for connector failures (HTTP, protocol, config)."""


class ConnectorAuthError(ConnectorError):
    """Authentication failed or credentials are missing/incomplete."""


class MappingError(Exception):
    """One external record could not be mapped to ReconDesk's schema.

    The sync logs these and continues with the next record; it never
    crashes the whole run for one bad record.
    """

    def __init__(self, record_id, field, reason):
        self.record_id = str(record_id) if record_id is not None else None
        self.field = field
        self.reason = reason
        super().__init__(f"record {self.record_id}: {field}: {reason}")
