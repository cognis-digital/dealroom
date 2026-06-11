"""dealroom MCP server.

Exposes the due-diligence engine as an MCP capability over stdio using
newline-delimited JSON-RPC 2.0. Standard library only — no SDK required — so it
runs anywhere Python does and can be wired into Cognis.Studio, Claude Desktop,
or Cursor as a local MCP server:

    {"command": "python", "args": ["-m", "dealroom", "mcp"]}

Implemented methods:
  * initialize     — handshake, advertises the tools capability
  * tools/list     — describes `checklist` and `scan_dataroom`
  * tools/call     — runs a tool and returns its result as JSON text
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

from . import TOOL_NAME, TOOL_VERSION
from .core import (
    DEAL_TYPES,
    DataroomError,
    checklist_to_dict,
    scan_dataroom,
)

PROTOCOL_VERSION = "2024-11-05"

_TOOLS = [
    {
        "name": "checklist",
        "description": "Generate a structured M&A/VC diligence checklist for a "
                       "deal type (saas / services / hardware). Returns the "
                       "ordered checklist items with categories and required flags.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "deal_type": {
                    "type": "string",
                    "enum": list(DEAL_TYPES),
                    "description": "Deal type to scaffold a checklist for.",
                }
            },
            "required": ["deal_type"],
            "additionalProperties": False,
        },
    },
    {
        "name": "scan_dataroom",
        "description": "Inventory a local dataroom directory, map files to the "
                       "diligence checklist, flag missing required items and "
                       "risky document patterns (auto-renew, change-of-control, "
                       "unlimited liability, missing IP assignment, expiring "
                       "contracts). Returns a status + risk report as JSON.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Path to the local dataroom directory.",
                },
                "deal_type": {
                    "type": "string",
                    "enum": list(DEAL_TYPES),
                    "description": "Deal type checklist to apply.",
                },
            },
            "required": ["directory", "deal_type"],
            "additionalProperties": False,
        },
    },
]


def _result(req_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "checklist":
        deal_type = arguments.get("deal_type")
        if not isinstance(deal_type, str) or not deal_type:
            raise ValueError("`deal_type` (string) is required")
        payload = checklist_to_dict(deal_type)
        is_error = False
    elif name == "scan_dataroom":
        directory = arguments.get("directory")
        deal_type = arguments.get("deal_type")
        if not isinstance(directory, str) or not directory:
            raise ValueError("`directory` (string path) is required")
        if not isinstance(deal_type, str) or not deal_type:
            raise ValueError("`deal_type` (string) is required")
        payload = scan_dataroom(directory, deal_type).to_dict()
        is_error = bool(payload.get("summary", {}).get("failed"))
    else:
        raise ValueError(f"unknown tool: {name}")

    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
        "isError": is_error,
    }


def handle_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Dispatch a single JSON-RPC request. Returns None for notifications."""
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}
    is_notification = "id" not in req

    if method == "initialize":
        res = _result(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": TOOL_NAME, "version": TOOL_VERSION},
        })
        return None if is_notification else res

    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "ping":
        return None if is_notification else _result(req_id, {})

    if method == "tools/list":
        return _result(req_id, {"tools": _TOOLS})

    if method == "tools/call":
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        try:
            return _result(req_id, _call_tool(name, arguments))
        except (ValueError, OSError, DataroomError) as exc:
            return _error(req_id, -32602, str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            return _error(req_id, -32603, f"internal error: {exc}")

    if is_notification:
        return None
    return _error(req_id, -32601, f"method not found: {method}")


def run_mcp_server(stdin=None, stdout=None) -> None:
    """Read newline-delimited JSON-RPC from stdin, write responses to stdout."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(_error(None, -32700, "parse error")) + "\n")
            stdout.flush()
            continue
        response = handle_request(req)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


if __name__ == "__main__":
    run_mcp_server()
