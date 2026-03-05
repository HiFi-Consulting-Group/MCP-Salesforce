# MCP Salesforce Connector

A Model Context Protocol (MCP) server implementation for Salesforce integration, allowing LLMs to interact with Salesforce data through SOQL queries and SOSL searches.

## Features

- Execute SOQL (Salesforce Object Query Language) queries
- Perform SOSL (Salesforce Object Search Language) searches
- Retrieve metadata for Salesforce objects, including field names, labels, and types
- Retrieve, create, update, and delete records
- Execute Tooling API requests
- Execute Apex REST requests
- Make direct REST API calls to Salesforce


## Authentication

This server uses the **OAuth Authorization Code + Refresh Token** flow exclusively.
Users authenticate once via browser; the server auto-refreshes the access token on
every startup.  No passwords are ever stored.

### Step 1: Create a Salesforce External Client App

Salesforce has replaced Connected Apps with **External Client Apps**. In Salesforce Setup, search for **External Client Apps** and create a new one:

- Under **OAuth Settings**, enable **OAuth Authorization Code and Credentials Flow**
- Callback URL: `http://localhost:8788/callback`
- Scopes: `api`, `refresh_token`, `offline_access`
- Save and note the **Client ID** (Consumer Key) and **Client Secret** (Consumer Secret)

### Step 2: Run the one-time auth script

```bash
export SALESFORCE_MCP_CLIENT_ID=your_consumer_key
export SALESFORCE_MCP_CLIENT_SECRET=your_consumer_secret
# For a sandbox org, also set:
# export SALESFORCE_DOMAIN=test

uv run scripts/get_token.py
```

The script opens your browser, completes the OAuth flow, and prints the values
to add to your `.env` file or MCP server config.

### Step 3: Configure the MCP server

In your `claude_desktop_config.json` (or equivalent):

```json
{
    "mcpServers": {
        "salesforce": {
            "command": "uvx",
            "args": [
                "--from",
                "mcp-salesforce-connector",
                "salesforce"
            ],
            "env": {
                "SALESFORCE_INSTANCE_URL": "https://yourorg.my.salesforce.com",
                "SALESFORCE_MCP_CLIENT_ID": "your_consumer_key",
                "SALESFORCE_MCP_CLIENT_SECRET": "your_consumer_secret",
                "SALESFORCE_REFRESH_TOKEN": "your_refresh_token"
            }
        }
    }
}
```

The refresh token is long-lived (until revoked).  You only need to re-run the
script if a user changes their password or an admin revokes OAuth tokens.

## Environment Variable Reference

| Variable | Description |
|---|---|
| `SALESFORCE_MCP_CLIENT_ID` | External Client App Client ID (Consumer Key) |
| `SALESFORCE_MCP_CLIENT_SECRET` | External Client App Client Secret (Consumer Secret) |
| `SALESFORCE_REFRESH_TOKEN` | Long-lived refresh token (from `scripts/get_token.py`) |
| `SALESFORCE_INSTANCE_URL` | Your org's My Domain URL (e.g. `https://yourorg.my.salesforce.com`) |
| `SALESFORCE_DOMAIN` | Set to `test` for a sandbox org; omit for production |
