# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a Python-based Telegram MCP (Model Context Protocol) server that provides programmatic access to Telegram functionality through STDIO-based JSON-RPC communication. The server implements the MCP protocol to expose Telegram operations as tools that can be called by compatible clients.

## Architecture

The project is structured as a single Python package located in `telegram_mcp_server_py/` with the following key components:

### Core Files
- `main.py` - Entry point and MCP server implementation with STDIO framing
- `tools.py` - Telegram tool implementations (message reading, sending, forwarding, etc.)
- `utils.py` - Telegram client setup and session management
- `config.py` - Environment variable loading and validation
- `resources.py` - Resource handlers (currently placeholders)
- `cli_login.py` - Standalone CLI utility for interactive Telegram authentication

### Communication Protocol
The server uses STDIO transport with JSON-RPC 2.0 framing:
- stdout: Reserved exclusively for MCP protocol frames
- stderr: All logging and debug output
- Framing: `Content-Length: <bytes>\r\n\r\n{json_payload}`

## Development Commands

### Setup and Installation
```bash
# Install dependencies
pip install -r telegram_mcp_server_py/requirements.txt

# Run the MCP server (use unbuffered mode)
python -u -m telegram_mcp_server_py.main

# Interactive login for user authentication
python -m telegram_mcp_server_py.cli_login --api-id <ID> --api-hash <HASH> --phone <PHONE>

# Bot authentication
python -m telegram_mcp_server_py.cli_login --bot-token "<TOKEN>"
```

### Environment Configuration
Create `telegram_mcp_server_py/.env` with:
- Bot mode: `TELEGRAM_BOT_TOKEN`
- User mode: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE_NUMBER`
- Optional: `TELEGRAM_SESSION_FILE` (defaults to `session.txt`)

## Available Tools

The server exposes these MCP tools:
- `tg.resolve_chat` - Resolve chat identifiers
- `tg.read_messages` / `tg.fetch_history` - Read chat history
- `tg.send_message` - Send messages
- `tg.forward_message` - Forward messages
- `tg.mark_read` - Mark messages as read
- `tg.get_unread_count` - Get unread message counts
- `tg.get_chats` - List available chats

## Key Implementation Details

### Session Management
- Sessions are persisted as string files (`session.txt` by default)
- Bot authentication is recommended for simplicity
- User authentication requires interactive login via `cli_login.py`

### Error Handling
- All errors are logged to stderr
- MCP protocol responses follow the format: `{"content": [{"type": "text", "text": "json_string"}]}`
- The server waits for Telegram client readiness before processing tool calls

### Compatibility Notes
- Compatible with Node.js MCP client implementations
- Tool names and arguments match the reference Node.js server
- Supports both camelCase and snake_case argument variants

## Testing

Since this is an MCP server intended for integration with external clients, testing typically involves:
1. Running the server manually and verifying MCP protocol compliance
2. Using MCP client implementations to test tool functionality
3. Verifying session persistence and authentication flows

The server outputs readiness indicators to stderr: "Telegram client ready, tools registered."