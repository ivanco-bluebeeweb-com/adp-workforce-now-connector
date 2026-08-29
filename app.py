"""Extension declaration, secrets, lifecycle hooks.

WHY BYOK (bring-your-own-key), same reasoning as Gusto/Xero/Sage Intacct/
QuickBooks/Clio Connector. The user's ADP Workforce Now organisation data
lives inside THEIR OWN ADP account -- Imperal cannot broker a shared ADP
Marketplace partnership centrally (that requires ADP's own formal partner
certification, confirmed from marketplace-cdn.adp.com's Partner
Development Learning Guide, chapter 5).

WHY OAUTH2 CLIENT CREDENTIALS + MUTUAL TLS, NOT AUTHORIZATION CODE
(confirmed against developers.adp.com/articles/general/access-tokens plus
independent third-party integration docs -- Nexla, Apideck, Unified.to,
and the node-adp-workforce-now client library -- all describing the same
shape, 2026-08-29). Unlike Gusto/Xero/QuickBooks/Sage Intacct (browser
redirect + user consent), ADP is a backend-to-backend service flow: no
redirect at all. But EVERY call to api.adp.com and accounts.adp.com,
including the token endpoint itself, requires a client TLS certificate
(PEM cert + matching private key) issued by ADP for that specific
application registration -- plain OAuth2 credentials alone are rejected.

WHY THE USER BRINGS FOUR CREDENTIALS, NOT TWO. client_id + client_secret
(same as everywhere else) PLUS a PEM certificate and its matching PEM
private key. All four are registered as write-only secrets -- never
echoed back once saved, same convention as client_secret elsewhere.

WHY THERE IS NO REFRESH_TOKEN HANDLING HERE. Client Credentials Grant has
no refresh_token concept -- when the short-lived access_token (~3600s)
expires, the connector simply re-runs the full client-credentials + mTLS
exchange from scratch rather than exchanging a refresh_token.
"""
from __future__ import annotations

from imperal_sdk import ChatExtension, Extension

ext = Extension(
    "adp-workforce-now-connector",
    version="0.1.0",
    display_name="ADP Workforce Now",
    icon="icon.svg",
    capabilities=["adp:read"],
    description=(
        "Connect your own ADP Workforce Now organisation (OAuth2 Client Credentials + mutual TLS) to read "
        "workers, payroll instructions, time-off requests, and organisational data, plus value-add workforce "
        "reports. Requires your own ADP application's Client ID/Secret and a client certificate issued by ADP."
    ),
)

chat = ChatExtension(ext, tool_name="adp_workforce_now")

ext.secret(
    "adp_connections", "JSON array of saved ADP Workforce Now connections (client_id/secret, cert/key, tokens).",
    required=False, write_mode="extension", max_bytes=65536, rotation_hint_days=365,
)


@ext.health_check
async def health_check(ctx):
    raw = await ctx.secrets.get("adp_connections")
    return {"ok": True, "has_connections": bool(raw)}
