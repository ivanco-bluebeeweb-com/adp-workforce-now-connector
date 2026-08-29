# ADP Workforce Now Connector -- Preparation (v0.1)

## API surface
ADP API Central (api.adp.com), HCM Offerings WFN API family (HR, Payroll,
Time & Attendance, Benefits, Recruiting where entitled). Confirmed via
developers.adp.com (2026-08-29).

## Auth model -- DIFFERENT FROM GUSTO/XERO/QBO/SAGE INTACCT
ADP uses **OAuth2 Client Credentials Grant + mutual TLS (mTLS)** -- NOT
Authorization Code. Confirmed from developers.adp.com/articles/general/
access-tokens and multiple third-party integration docs (Nexla, Apideck,
Unified.to, node-adp-workforce-now library), all independently describing
the same shape:
- No browser redirect / user consent screen. A backend service-to-service
  flow: exchange Client ID + Client Secret directly at the token endpoint
  for an access_token.
- BUT every call to api.adp.com AND accounts.adp.com (including the token
  endpoint itself) requires a client TLS certificate (PEM cert + private
  key) issued by ADP for that specific application registration --
  ordinary API-key/OAuth2 alone is rejected without the certificate
  handshake.
- This means BYOK here means the user brings FOUR things: client_id,
  client_secret, a PEM certificate, and its matching PEM private key --
  not just two fields like Gusto/Xero/QuickBooks.

## Why this is still BYOK, same reasoning as every other connector
The user's own ADP Workforce Now organisation data lives inside THEIR
OWN ADP account. Imperal cannot broker a shared ADP Marketplace
partnership centrally (that requires ADP's own formal partner
certification process, chapter 5 of the Marketplace guide). Each user
registers their own application in ADP's Partner/Developer portal,
downloads/generates their own client certificate, and pastes all four
credentials here.

## Token lifetime & refresh
Client Credentials tokens are short-lived (typically ~3600s) and are
simply re-requested from scratch when expired -- there is no
refresh_token concept in this grant type (unlike Authorization Code).
ensure_fresh_token here re-runs the full client-credentials + mTLS
exchange rather than a refresh_token exchange.

## Entity coverage
ADP's HCM APIs are resource/event-oriented (workers, payroll, time-off),
much less uniform than QBO. Plan:
- Generic layer: GET-heavy (workers, payroll-instructions,
  time-off-requests) via the entity_path registry pattern already
  established in gusto_client.py.
- First-class: get_worker, list_workers, get_company_info-equivalent
  (list_organizational_units or similar), value-add reports:
  get_worker_headcount_report, get_upcoming_hires_report (if event data
  supports it) -- to be finalized once entity paths are picked from
  ADP's API Explorer.

## Certificate storage
The PEM cert and private key are stored as two additional secret fields
per connection (write-only, never echoed back), same write-only
convention as client_secret elsewhere.
