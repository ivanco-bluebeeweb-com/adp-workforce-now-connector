"""Pydantic params/result models for ADP Workforce Now Connector.

All params models are module-scope (V17 federal invariant, same rule as
Gusto/Xero/Sage Intacct Connector's schemas.py).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class NoParams(BaseModel):
    """Explicit empty params model -- V17 disallows untyped handlers."""
    pass


class ConnectionScoped(BaseModel):
    connection_id: str = Field(
        "",
        description="Which connected ADP organisation to use (see list_connections). Omit if only one is connected.",
    )


# ──────────────────────────────────────────────────────────────────────────
# Connection -- 4 credentials (client_id, client_secret, cert, key), no
# browser redirect (Client Credentials + mTLS, unlike every other
# connector in this portfolio so far).
# ──────────────────────────────────────────────────────────────────────────


class ConnectAdpParams(BaseModel):
    client_id: str = Field("", description="Your ADP application's Client ID (developers.adp.com).")
    client_secret: str = Field("", description="Your ADP application's Client Secret.")
    cert_pem: str = Field("", description="Your ADP application's client certificate, full PEM text including BEGIN/END lines.")
    key_pem: str = Field("", description="Your ADP application's private key matching the certificate, full PEM text including BEGIN/END lines.")
    label: str = Field("", description="Optional friendly label for this connection, e.g. 'Acme Inc ADP'.")


class ProviderConnection(BaseModel):
    id: str = ""
    label: str = ""
    org_name: str = ""


class ProviderConnectionList(BaseModel):
    connections: list[ProviderConnection] = Field(default_factory=list)


class DisconnectAdpParams(BaseModel):
    connection_id: str = Field(description="Which connection to disconnect (see list_connections).")


class DeleteResult(BaseModel):
    deleted: bool = True


# ──────────────────────────────────────────────────────────────────────────
# Generic entity layer (ADP HCM Offerings WFN API, read-heavy + a few
# supported writes)
# ──────────────────────────────────────────────────────────────────────────


class ListEntitiesParams(ConnectionScoped):
    entity: str = Field(description="ADP resource name, e.g. 'workers', 'payroll-workers', 'time-off-requests', 'events'.")
    filter_expr: str = Field("", description="Optional ADP $filter query expression, e.g. \"workers/workAssignments/homeOrganizationalUnits/name eq 'Sales'\".")
    limit: int = Field(100, description="Max records to return (ADP's own page size applies if omitted).")


class EntityList(BaseModel):
    entity: str = ""
    rows: list[dict] = Field(default_factory=list)
    count: int = 0


class GetEntityParams(ConnectionScoped):
    entity: str = Field(description="ADP resource name, e.g. 'workers'.")
    entity_id: str = Field(description="The record's ADP identifier (AOID for workers).")


class EntityDetail(BaseModel):
    entity: str = ""
    data: dict = Field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────
# Value-add reports
# ──────────────────────────────────────────────────────────────────────────


class GetOrgInfoParams(ConnectionScoped):
    pass


class OrgInfo(BaseModel):
    org_name: str = ""
    worker_count: int = 0


class HeadcountReport(BaseModel):
    total_workers: int = 0
    by_status: dict = Field(default_factory=dict)


class UpcomingReviewsReport(BaseModel):
    upcoming: list[dict] = Field(default_factory=list)
