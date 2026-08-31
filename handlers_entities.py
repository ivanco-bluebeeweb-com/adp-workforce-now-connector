"""Generic entity read layer for ADP Workforce Now Connector -- workers,
payroll-workers, time-off-requests, events, organizational-units,
pay-statements, using adp_client's per-resource path map.

WHY READ-ONLY THIS RELEASE. ADP's HCM Offerings WFN write APIs (e.g.
worker onboarding, time-off approval) require specific entitlements per
application registration and go through ADP's own multi-step Event
Notification / Business Context Data flows rather than plain REST POST --
out of scope for v1. This connector covers the read surface plus the
value-add reports in handlers_reports.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import adp_client as ac
from app import chat
from handlers_connection import resolve_or_error
from schemas import (
    ListEntitiesParams, EntityList,
    GetEntityParams, EntityDetail,
)


@chat.function(
    "list_entities",
    "List ADP Workforce Now records of any resource type (workers, payroll-workers, time-off-requests, "
    "events, organizational-units, pay-statements). time-off-requests and pay-statements need a worker's "
    "AOID passed via filter_expr in ADP's own $filter syntax.",
    action_type="read", chain_callable=True, data_model=EntityList,
)
async def list_entities(ctx, params: ListEntitiesParams) -> ActionResult:
    """List ADP records of a given resource type."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if not conn:
        return err
    path = ac.entity_path(params.entity)
    if not path:
        return ActionResult.error(
            f"Unknown ADP resource '{params.entity}'. Known resources: {', '.join(ac.known_entities())}.",
            code="ADP_VALIDATION_FAILED",
        )
    q = {"$filter": params.filter_expr} if params.filter_expr else None
    data = await ac.request(ctx, conn, "GET", path, params=q, action="list " + params.entity)
    rows = []
    if isinstance(data, dict):
        for key in data:
            if isinstance(data[key], list):
                rows = data[key]
                break
    elif isinstance(data, list):
        rows = data
    if params.limit and len(rows) > params.limit:
        rows = rows[:params.limit]
    return ActionResult.success(EntityList(entity=params.entity, rows=rows, count=len(rows)), summary="Entities listed.")


@chat.function(
    "get_entity",
    "Read one ADP Workforce Now record of any resource type in full by its identifier (AOID for workers).",
    action_type="read", chain_callable=True, data_model=EntityDetail,
)
async def get_entity(ctx, params: GetEntityParams) -> ActionResult:
    """Read one ADP record by id -- appends /{id} to the resource's base path."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if not conn:
        return err
    path = ac.entity_path(params.entity)
    if not path:
        return ActionResult.error(
            f"Unknown ADP resource '{params.entity}'. Known resources: {', '.join(ac.known_entities())}.",
            code="ADP_VALIDATION_FAILED",
        )
    data = await ac.request(ctx, conn, "GET", f"{path}/{params.entity_id}", action="get " + params.entity)
    return ActionResult.success(EntityDetail(entity=params.entity, data=data if isinstance(data, dict) else {}), summary="Entity retrieved.")
