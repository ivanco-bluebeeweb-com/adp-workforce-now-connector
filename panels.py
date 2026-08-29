"""Panel UI -- connections list/connect form + the one required "App
settings" entry point, same shape as Gusto/Xero/Sage Intacct/QuickBooks
Connector's panels.py.

SIDEBAR CONTENT -- NO CARDS ANYWHERE, per ~/UI_INTERFACE_STANDARD.md's
"left sidebar, no decorated cards" rule. Every section is a plain
ui.Stack, sections separated by ui.Divider() -- no Card border/background/
shadow anywhere in this slot. Disconnect lives only in the "App settings"
screen (panels_settings.py). The one secondary "App settings" button is
always the LAST element at the bottom of the sidebar.

PER ~/UI_INTERFACE_STANDARD.md (2026-08-21 addendum): every Input carries
its own visible label (never placeholder-only), the placeholder text is
always contextually specific. The "How do I set this up?" instructions
live ONLY in the help modal below -- never duplicated as static sidebar
text. ADP's connect form needs 4 fields (client_id, client_secret, plus
two multi-line PEM blocks) -- both PEM fields use ui.Textarea, not
ui.Input, since certificate/key content spans many lines.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
import handlers_connection as h


def _settings_button() -> ui.UINode:
    return ui.Button(
        "App settings", variant="secondary", size="sm", full_width=True,
        icon="settings", on_click=ui.Call("__panel__adp_settings"),
    )


def _connection_row(c: dict) -> ui.UINode:
    label = c.get("label") or "ADP connection"
    return ui.Stack(direction="v", gap=1, children=[
        ui.Text(label, variant="body"),
        ui.Text("Connected", variant="caption"),
    ])


def _connections_section(connections: list[dict]) -> ui.UINode:
    if not connections:
        return ui.Text("No ADP organisations connected yet.", variant="caption")
    children: list[ui.UINode] = []
    for i, c in enumerate(connections):
        if i > 0:
            children.append(ui.Divider())
        children.append(_connection_row(c))
    return ui.Stack(direction="v", gap=2, children=children)


@ext.panel("adp_connect", slot="left", title="ADP Workforce Now")
async def adp_connect_panel(ctx, **kwargs) -> object:
    connections = await h._load_connections(ctx)
    return ui.Stack(direction="v", gap=4, children=[
        ui.Header("ADP Workforce Now", level=2, subtitle="HR & payroll data, connected to your own org"),
        _connections_section(connections),
        ui.Divider(),
        ui.Button(
            "How do I set this up?", variant="ghost", size="sm",
            on_click=ui.Call("__panel__adp_connect_help"),
        ),
        ui.Form(
            action="connect_adp",
            submit_label="Connect ADP",
            fields=[
                ui.Input(name="client_id", label="ADP application Client ID", placeholder="Paste your ADP app's Client ID"),
                ui.Password(name="client_secret", label="ADP application Client Secret", placeholder="Paste your ADP app's Client Secret"),
                ui.Textarea(name="cert_pem", label="Client certificate (PEM)", placeholder="-----BEGIN CERTIFICATE-----\n..."),
                ui.Textarea(name="key_pem", label="Private key (PEM)", placeholder="-----BEGIN PRIVATE KEY-----\n..."),
                ui.Input(name="label", label="Label (optional)", placeholder="e.g. Acme Inc ADP"),
            ],
        ),
        ui.Divider(),
        _settings_button(),
    ])


@ext.panel("adp_connect_help", slot="overlay", title="How do I set this up?")
async def adp_connect_help(ctx, **kwargs) -> object:
    content = ui.Stack(direction="v", gap=3, children=[
        ui.Text("1. Go to developers.adp.com, sign in, and register a new application."),
        ui.Text("2. Generate (or upload) a client certificate for your application -- ADP requires mutual TLS on every call, not just an API key."),
        ui.Text("3. Copy the application's Client ID and Client Secret, plus the full PEM text of the certificate and its matching private key."),
        ui.Text("4. Paste all four into the form on the left and click \"Connect ADP\" -- there's no browser login step here, the connection is validated and finished immediately."),
        ui.Divider(),
        ui.Alert(
            title="Read-heavy in this release",
            message=(
                "Workers, payroll workers, time off requests, events, "
                "organizational units, and pay statements are all covered "
                "for reading. Write operations (onboarding, approvals) go "
                "through ADP's own multi-step flows and are not yet "
                "automated here."
            ),
            type="info",
        ),
    ])
    return ui.Stack(direction="v", gap=2, children=[content])
