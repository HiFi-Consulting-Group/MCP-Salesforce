#!/usr/bin/env python3
"""One-time OAuth Authorization Code flow to obtain a Salesforce refresh token.

Run this script once to authenticate via browser.  It will print the env vars
you need to add to your .env file or MCP server config.  After that the MCP
server auto-refreshes its access token on every start — no passwords stored.

Usage:
    uv run scripts/get_token.py
    # or
    python scripts/get_token.py

Required env vars (set before running, or edit the defaults below):
    SALESFORCE_MCP_CLIENT_ID      - Connected App Consumer Key
    SALESFORCE_MCP_CLIENT_SECRET  - Connected App Consumer Secret

Optional:
    SALESFORCE_DOMAIN         - Set to "test" for a sandbox org
    OAUTH_REDIRECT_PORT       - Local callback port (default: 8788)

Salesforce External Client App requirements:
    - OAuth Authorization Code and Credentials Flow enabled
    - Callback URL: http://localhost:8788/callback  (or your chosen port)
    - Scopes: api, refresh_token, offline_access
"""

import base64
import hashlib
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser


def _pkce_pair() -> tuple[str, str]:
    """Return a (code_verifier, code_challenge) pair for PKCE (RFC 7636)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge

CLIENT_ID = os.getenv("SALESFORCE_MCP_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SALESFORCE_MCP_CLIENT_SECRET", "")
DOMAIN = os.getenv("SALESFORCE_DOMAIN", "")
PORT = int(os.getenv("OAUTH_REDIRECT_PORT", "8788"))

REDIRECT_URI = f"http://localhost:{PORT}/callback"
SF_BASE = "https://test.salesforce.com" if DOMAIN == "test" else "https://login.salesforce.com"

_auth_code: list[str] = []
_auth_done = threading.Event()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _auth_code.append(params["code"][0])
            body = b"<html><body><h2>Authentication complete! You can close this tab.</h2></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif "error" in params:
            error = params.get("error", ["unknown"])[0]
            desc = params.get("error_description", [error])[0]
            body = f"<html><body><h2>Error: {desc}</h2></body></html>".encode()
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

        _auth_done.set()

    def log_message(self, format: str, *args: object) -> None:
        pass  # suppress access logs


def main() -> None:
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: SALESFORCE_MCP_CLIENT_ID and SALESFORCE_MCP_CLIENT_SECRET must be set.\n")
        print("In your Salesforce External Client App (Setup > External Client Apps), ensure:")
        print("  - OAuth Authorization Code and Credentials Flow is enabled")
        print(f"  - Callback URL includes: {REDIRECT_URI}")
        print("  - Scopes include: api, refresh_token, offline_access")
        sys.exit(1)

    code_verifier, code_challenge = _pkce_pair()

    auth_url = (
        f"{SF_BASE}/services/oauth2/authorize"
        f"?response_type=code"
        f"&client_id={urllib.parse.quote(CLIENT_ID)}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&scope={urllib.parse.quote('api refresh_token offline_access')}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    server = http.server.HTTPServer(("localhost", PORT), _CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    print(f"Opening browser for Salesforce login ({SF_BASE})...")
    print(f"If the browser does not open automatically, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    timed_out = not _auth_done.wait(timeout=300)
    server.shutdown()

    if timed_out or not _auth_code:
        print("Error: Timed out waiting for auth code. Did you complete the browser login?")
        sys.exit(1)

    # Exchange authorization code for tokens
    token_url = f"{SF_BASE}/services/oauth2/token"
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": _auth_code[0],
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }).encode()

    try:
        req = urllib.request.Request(token_url, data=body, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        print(f"Error exchanging authorization code for tokens: {exc}")
        sys.exit(1)

    if "error" in data:
        print(f"Token exchange failed: {data.get('error_description', data['error'])}")
        sys.exit(1)

    access_token: str = data.get("access_token", "")
    refresh_token: str = data.get("refresh_token", "")
    instance_url: str = data.get("instance_url", "")

    if not access_token:
        print(f"Unexpected response — no access_token: {data}")
        sys.exit(1)

    print("Authentication successful!\n")
    print("=" * 60)
    print("Add the following to your .env file or MCP server config:")
    print("=" * 60)
    print(f"SALESFORCE_INSTANCE_URL={instance_url}")
    print(f"SALESFORCE_MCP_CLIENT_ID={CLIENT_ID}")
    print(f"SALESFORCE_MCP_CLIENT_SECRET={CLIENT_SECRET}")

    if refresh_token:
        print(f"SALESFORCE_REFRESH_TOKEN={refresh_token}")
        print()
        print("With SALESFORCE_REFRESH_TOKEN set, the MCP server will")
        print("automatically exchange it for a fresh access token on startup.")
        print("You do not need to re-run this script unless the refresh token")
        print("is revoked (e.g. password change, token expiry policy).")
    else:
        print(f"SALESFORCE_ACCESS_TOKEN={access_token}")
        print()
        print("Note: No refresh_token was returned. Make sure your External")
        print("Client App has the 'offline_access' (or 'refresh_token') scope enabled.")

    print("=" * 60)


if __name__ == "__main__":
    main()
