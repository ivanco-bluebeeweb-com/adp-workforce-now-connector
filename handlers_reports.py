"""Org info + value-add reports for ADP Workforce Now Connector -- same
"value-add on top of raw API" shape as Gusto/Xero/Sage Intacct Connector's
handlers_reports.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import adp_client as ac
from app import chat
from handlers_connection import resolve_or_error
from schemas import (
    GetOrgInfoParams, OrgInfo,
    HeadcountReport,
    UpcomingReviewsReport,
)


@chat.function(
    "get_org_info",
    "Read the connected ADP Workforce Now organisation's own profile: organisation name and total worker "
    "count.",
    action_type="read", chain_callable=True, data_model=OrgInfo,
)
async def get_org_info(ctx, params: GetOrgInfoParams) -> ActionResult:
    """Read basic org profile info via the workers list count."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if not conn:
        return err
    data = await ac.request(ctx, conn, "GET", "/hr/v2/workers", params={"$top": "1"}, action="get org info")
    workers = data.get("workers", []) if isinstance(data, dict) else []
    meta = data.get("meta", {}) if isinstance(data, dict) else {}
    total = meta.get("totalNumber", len(workers)) if isinstance(meta, dict) else len(workers)
    return ActionResult.ok(OrgInfo(org_name=conn.get("org_name", ""), worker_count=int(total or 0)))


@chat.function(
    "get_headcount_report",
    "Value-add report: one-glance headcount for the connected ADP organisation -- total worker count "
    "broken down by work assignment status (active/terminated/etc).",
    action_type="read", chain_callable=True, data_model=HeadcountReport,
)
async def get_headcount_report(ctx, params: GetOrgInfoParams) -> ActionResult:
    """Scan workers and bucket them by their work assignment status code."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if not conn:
        return err
    data = await ac.request(ctx, conn, "GET", "/hr/v2/workers", params={"$top": "200"}, action="headcount report")
    workers = data.get("workers", []) if isinstance(data, dict) else []
    by_status: dict = {}
    for w in workers:
        assignments = w.get("workAssignments", []) if isinstance(w, dict) else []
        status = "unknown"
        if assignments:
            status_obj = assignments[0].get("assignmentStatus", {}) if isinstance(assignments[0], dict) else {}
            status = status_obj.get("statusCode", {}).get("codeValue", "unknown") if isinstance(status_obj, dict) else "unknown"
        by_status[status] = by_status.get(status, 0) + 1
    return ActionResult.ok(HeadcountReport(total_workers=len(workers), by_status=by_status))


@chat.function(
    "get_upcoming_reviews_report",
    "Value-add report: read ADP event-notification-messages filtered to upcoming performance-review-style "
    "events, so HR can see who's due for review soon without combing through raw events.",
    action_type="read", chain_callable=True, data_model=UpcomingReviewsReport,
)
async def get_upcoming_reviews_report(ctx, params: GetOrgInfoParams) -> ActionResult:
    """Read event-notification-messages and surface anything review-related."""
    conn, err = await resolve_or_error(ctx, params.connection_id)
    if not conn:
        return err
    data = await ac.request(ctx, conn, "GET", "/core/v1/event-notification-messages", action="upcoming reviews report")
    events = data.get("events", []) if isinstance(data, dict) else []
    upcoming = [e for e in events if isinstance(e, dict) and "review" in str(e.get("data", {})).lower()]
    return ActionResult.ok(UpcomingReviewsReport(upcoming=upcoming))
