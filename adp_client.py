"""Thin HTTP client for the ADP Workforce Now (HCM Offerings WFN) API +
OAuth2 Client Credentials + mutual TLS helpers.

Same "fail()-dict + ClientFail exception + generic request() helper" shape
as gusto_client.py / sage_intacct_client.py / xero_client.py, but with an
extra wrinkle: EVERY request (including the token exchange itself) must
present a client TLS certificate + private key, confirmed from
developers.adp.com/articles/general/access-tokens (2026-08-29).
"""
from __future__ import annotations

import tempfile
from typing import Any

import httpx

TOKEN_URL = "https://accounts.adp.com/auth/oauth/v2/token"
API_BASE = "https://api.adp.com"

ADP_NOT_CONNECTED = "ADP_NOT_CONNECTED"
ADP_UNAUTHORIZED = "ADP_UNAUTHORIZED"
ADP_FORBIDDEN = "ADP_FORBIDDEN"
ADP_NOT_FOUND = "ADP_NOT_FOUND"
ADP_RATE_LIMITED = "ADP_RATE_LIMITED"
ADP_BACKEND_ERROR = "ADP_BACKEND_ERROR"
ADP_VALIDATION_FAILED = "ADP_VALIDATION_FAILED"
ADP_RESPONSE_UNEXPECTED = "ADP_RESPONSE_UNEXPECTED"
ADP_CERT_INVALID = "ADP_CERT_INVALID"

_MESSAGES = {
    ADP_NOT_CONNECTED: "No ADP Workforce Now connection found. Connect ADP first.",
    ADP_UNAUTHORIZED: "ADP rejected the request as unauthorized -- the connection may need to be reconnected.",
    ADP_FORBIDDEN: "ADP denied access to this resource for the current application's entitlements.",
    ADP_NOT_FOUND: "That ADP record was not found.",
    ADP_RATE_LIMITED: "ADP rate-limited this request. Try again shortly.",
    ADP_BACKEND_ERROR: "ADP's API returned an error.",
    ADP_VALIDATION_FAILED: "ADP rejected the request as invalid.",
    ADP_RESPONSE_UNEXPECTED: "ADP returned an unexpected response shape.",
    ADP_CERT_INVALID: "The client certificate/private key pair was rejected -- confirm they were pasted in full PEM format and match the application registration.",
}


class ClientFail(Exception):
    def __init__(self, payload: dict):
        super().__init__(payload.get("message", "ADP request failed"))
        self.payload = payload


def fail(code: str, detail: str = "") -> dict:
    message = _MESSAGES.get(code, "ADP request failed.")
    if detail:
        message = f"{message} ({detail})"
    return {"ok": False, "code": code, "message": message}


def parse_json_object(raw: str) -> tuple[bool, Any]:
    import json
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as e:
        return False, str(e)
    if not isinstance(data, dict):
        return False, "must be a JSON object"
    return True, data


def _write_temp_pem(content: str, suffix: str) -> str:
    """mTLS via httpx requires filesystem paths for cert/key, not raw PEM
    text -- so each request materializes short-lived temp files."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
    f.write(content)
    f.close()
    return f.name


def _client_cert(conn: dict) -> tuple[str, str] | None:
    cert_pem = conn.get("cert_pem", "")
    key_pem = conn.get("key_pem", "")
    if not cert_pem or not key_pem:
        return None
    cert_path = _write_temp_pem(cert_pem, ".pem")
    key_path = _write_temp_pem(key_pem, ".key")
    return cert_path, key_path


async def exchange_client_credentials(ctx, client_id: str, client_secret: str, cert_pem: str, key_pem: str) -> dict:
    """OAuth2 Client Credentials Grant, presented over mTLS -- no user
    browser redirect, unlike Gusto/Xero/QuickBooks/Sage Intacct."""
    import os
    cert_path = _write_temp_pem(cert_pem, ".pem")
    key_path = _write_temp_pem(key_pem, ".key")
    try:
        async with httpx.AsyncClient(timeout=30, cert=(cert_path, key_path)) as client:
            resp = await client.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code == 401:
            return fail(ADP_UNAUTHORIZED, "invalid client_id/client_secret")
        if resp.status_code >= 400:
            return fail(ADP_CERT_INVALID, f"HTTP {resp.status_code}")
        return resp.json()
    except httpx.TransportError as e:
        return fail(ADP_CERT_INVALID, str(e))
    finally:
        for p in (cert_path, key_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Accept": "application/json", "Content-Type": "application/json"}


def _check_status(resp: httpx.Response, action: str) -> Any:
    if resp.status_code == 401:
        raise ClientFail(fail(ADP_UNAUTHORIZED, action))
    if resp.status_code == 403:
        raise ClientFail(fail(ADP_FORBIDDEN, action))
    if resp.status_code == 404:
        raise ClientFail(fail(ADP_NOT_FOUND, action))
    if resp.status_code == 429:
        raise ClientFail(fail(ADP_RATE_LIMITED, action))
    if resp.status_code >= 500:
        raise ClientFail(fail(ADP_BACKEND_ERROR, f"{action}: HTTP {resp.status_code}"))
    if resp.status_code >= 400:
        raise ClientFail(fail(ADP_VALIDATION_FAILED, f"{action}: {resp.text[:200]}"))
    try:
        return resp.json() if resp.content else {}
    except ValueError:
        raise ClientFail(fail(ADP_RESPONSE_UNEXPECTED, f"{action}: non-JSON response"))


async def request(ctx, conn: dict, method: str, path: str, *, params: dict | None = None,
                   json_body: Any = None, action: str = "request") -> Any:
    import os
    access_token = conn.get("access_token", "")
    if not access_token:
        raise ClientFail(fail(ADP_NOT_CONNECTED))
    cert_pair = _client_cert(conn)
    if not cert_pair:
        raise ClientFail(fail(ADP_CERT_INVALID, "missing certificate/key on this connection"))
    cert_path, key_path = cert_pair
    url = f"{API_BASE}{path}"
    try:
        async with httpx.AsyncClient(timeout=30, cert=(cert_path, key_path)) as client:
            resp = await client.request(method, url, headers=_headers(access_token), params=params, json=json_body)
        return _check_status(resp, action)
    finally:
        for p in (cert_path, key_path):
            try:
                os.unlink(p)
            except OSError:
                pass


_ENTITY_PATHS = {
    "workers": "/hr/v2/workers",
    "payroll-workers": "/payroll/v1/workers",
    "time-off-requests": "/time/v2/workers/{worker_id}/time-off-requests",
    "events": "/core/v1/event-notification-messages",
    "organizational-units": "/core/v1/organizational-units",
    "pay-statements": "/payroll/v1/workers/{worker_id}/pay-statements",
}


def known_entities() -> list[str]:
    return sorted(_ENTITY_PATHS.keys())


def entity_path(entity: str, *, worker_id: str = "") -> str | None:
    template = _ENTITY_PATHS.get(entity)
    if not template:
        return None
    if "{worker_id}" in template:
        if not worker_id:
            return None
        return template.format(worker_id=worker_id)
    return template
