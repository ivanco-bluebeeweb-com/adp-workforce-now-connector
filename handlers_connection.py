"""Connection management for ADP Workforce Now Connector: connect/
disconnect/list.

WHY THIS IS SIMPLER THAN GUSTO/XERO/QUICKBOOKS/SAGE INTACCT'S FLOW. ADP
uses OAuth2 Client Credentials Grant (service-to-service), not
Authorization Code -- there is no browser redirect, no consent screen, no
webhook callback, and no `state`/pending-connection dance. connect_adp
performs the full token exchange synchronously and either succeeds
immediately or reports why it failed.
"""
from __future__ import annotations

import json
import time as _time
import uuid

from imperal_sdk import ActionResult

import adp_client as ac
from app import chat
from schemas import (
    NoParams,
    ConnectAdpParams,
    ProviderConnection, ProviderConnectionList,
    DisconnectAdpParams, DeleteResult,
)

_SECRET_NAME = "adp_connections"


async def _load_connections(ctx) -> list[dict]:
    raw = await ctx.secrets.get(_SECRET_NAME)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


async def _save_connections(ctx, connections: list[dict]) -> None:
    await ctx.secrets.set(_SECRET_NAME, json.dumps(connections))


async def resolve_connection(ctx, connection_id: str = "") -> dict | None:
    connections = await _load_connections(ctx)
    if not connections:
        return None
    if connection_id:
        for c in connections:
            if c.get("id") == connection_id:
                return c
        return None
    return connections[0]


async def ensure_fresh_token(ctx, conn: dict) -> dict:
    """Client Credentials tokens have no refresh_token -- re-exchange from
    scratch when within 60s of expiry, using the same stored cert/key."""
    expires_at = int(conn.get("expires_at", 0) or 0)
    if expires_at and expires_at - int(_time.time()) > 60:
        return conn
    result = await ac.exchange_client_credentials(
        ctx, conn["client_id"], conn["client_secret"], conn["cert_pem"], conn["key_pem"],
    )
    if "access_token" not in result:
        return conn
    conn["access_token"] = result["access_token"]
    conn["expires_at"] = int(_time.time()) + int(result.get("expires_in", 3600))
    connections = await _load_connections(ctx)
    for i, c in enumerate(connections):
        if c.get("id") == conn.get("id"):
            connections[i] = conn
            break
    await _save_connections(ctx, connections)
    return conn


def _connection_to_entity(c: dict) -> ProviderConnection:
    return ProviderConnection(
        id=c.get("id", ""),
        label=c.get("label") or "ADP connection",
        org_name=c.get("org_name", ""),
    )


async def resolve_or_error(ctx, connection_id: str = ""):
    conn = await resolve_connection(ctx, connection_id)
    if not conn:
        return None, ActionResult.error(
            "No ADP Workforce Now connection found. Connect one with connect_adp first.",
            code="ADP_NOT_CONNECTED",
        )
    conn = await ensure_fresh_token(ctx, conn)
    return conn, None


@chat.function(
    "connect_adp",
    "Connect your ADP Workforce Now organisation: register your ADP application's Client ID, Client "
    "Secret, and its client certificate + matching private key (both full PEM text) from developers.adp.com. "
    "Unlike most connectors here, ADP requires no browser login -- the connection is validated and finished "
    "immediately in this one call.",
    action_type="write",
    chain_callable=True,
    data_model=ProviderConnection,
    event="adp-workforce-now-connector.connect",
    effects=["adp.connection.created"],
)
async def connect_adp(ctx, params: ConnectAdpParams) -> ActionResult:
    """Validate the user's ADP application credentials + mTLS cert/key by
    performing a real Client Credentials token exchange, then save the
    connection if it succeeds."""
    if not all([params.client_id.strip(), params.client_secret.strip(), params.cert_pem.strip(), params.key_pem.strip()]):
        return ActionResult.error(
            "Client ID, Client Secret, certificate, and private key are all required.",
            code="ADP_MISSING_FIELDS",
        )
    result = await ac.exchange_client_credentials(
        ctx, params.client_id.strip(), params.client_secret.strip(),
        params.cert_pem.strip(), params.key_pem.strip(),
    )
    if "access_token" not in result:
        return ActionResult.error(
            result.get("message", "Could not connect ADP -- credentials or certificate were rejected."),
            code=result.get("code", "ADP_UNAUTHORIZED"),
        )
    conn = {
        "id": str(uuid.uuid4()),
        "label": params.label.strip(),
        "client_id": params.client_id.strip(),
        "client_secret": params.client_secret.strip(),
        "cert_pem": params.cert_pem.strip(),
        "key_pem": params.key_pem.strip(),
        "access_token": result["access_token"],
        "expires_at": int(_time.time()) + int(result.get("expires_in", 3600)),
        "org_name": "",
    }
    connections = await _load_connections(ctx)
    connections.append(conn)
    await _save_connections(ctx, connections)
    return ActionResult.success(_connection_to_entity(conn), summary="Adp connected.")


@chat.function(
    "list_connections",
    "List the connected ADP Workforce Now organisations.",
    action_type="read",
    chain_callable=True,
    data_model=ProviderConnectionList,
)
async def list_connections(ctx, params: NoParams) -> ActionResult:
    """List all saved ADP connections."""
    connections = await _load_connections(ctx)
    return ActionResult.success(ProviderConnectionList(connections=[_connection_to_entity(c) for c in connections]), summary="Connections listed.")


@chat.function(
    "disconnect_adp",
    "Disconnect an ADP Workforce Now organisation: deletes the saved Client ID/Client Secret/certificate/"
    "private key. Nothing in ADP itself is changed.",
    action_type="destructive",
    chain_callable=True,
    data_model=DeleteResult,
    event="adp-workforce-now-connector.disconnect",
    effects=["adp.connection.removed"],
)
async def disconnect_adp(ctx, params: DisconnectAdpParams) -> ActionResult:
    """Delete one saved ADP connection by id."""
    connections = await _load_connections(ctx)
    remaining = [c for c in connections if c.get("id") != params.connection_id]
    if len(remaining) == len(connections):
        return ActionResult.error("No such ADP connection.", code="ADP_NOT_CONNECTED")
    await _save_connections(ctx, remaining)
    return ActionResult.success(DeleteResult(deleted=True), summary="Adp disconnected.")
