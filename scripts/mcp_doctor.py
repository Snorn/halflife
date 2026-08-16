"""Diagnose an MCP server that will not attach.

Runs the same checks a harness does, in order, and stops at the first failure —
so the output names the problem rather than leaving you to infer it.

    .venv/bin/python scripts/mcp_doctor.py          # POSIX
    .venv\\Scripts\\python.exe scripts\\mcp_doctor.py  # Windows
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ok(msg: str) -> None:
    print(f"   OK   {msg}")


def _fail(msg: str, *, hint: str = "") -> None:
    print(f"   FAIL {msg}")
    if hint:
        print(f"        {hint}")


def find_executable() -> str | None:
    """The console script, in the venv running this or on PATH."""
    bindir = Path(sys.executable).parent
    for name in ("halflife-mcp.exe", "halflife-mcp"):
        candidate = bindir / name
        if candidate.exists():
            return str(candidate)
    return shutil.which("halflife-mcp")


def check_import() -> bool:
    print("1. package imports")
    try:
        from halflife.mcp_server import server  # noqa: F401
    except Exception as exc:  # pragma: no cover - diagnostic path
        _fail(
            f"{type(exc).__name__}: {exc}",
            hint='reinstall with: python -m pip install -e ".[dev]"',
        )
        return False
    _ok("halflife.mcp_server imported")
    return True


def check_executable() -> str | None:
    print("2. console script")
    exe = find_executable()
    if exe is None:
        _fail(
            "halflife-mcp not found",
            hint="the package is installed but its entry point is missing; reinstall it",
        )
        return None
    _ok(exe)
    return exe


def check_starts(exe: str) -> bool:
    """A server that crashes on startup looks identical to a bad path."""
    print("3. server starts")
    proc = subprocess.run(
        [exe],
        input="",
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode not in (0, None):
        _fail(f"exited with code {proc.returncode}")
        for line in (proc.stderr or "").strip().splitlines()[-12:]:
            print(f"        {line}")
        return False
    if proc.stdout.strip() and not proc.stdout.lstrip().startswith("{"):
        _fail(
            "wrote non-JSON to stdout, which corrupts the protocol stream",
            hint=f"first line: {proc.stdout.splitlines()[0][:80]}",
        )
        return False
    _ok("exits cleanly on closed stdin")
    return True


async def _handshake(exe: str) -> str:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    async with stdio_client(StdioServerParameters(command=exe, args=[])) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            return f"{init.server_info.name} {init.server_info.version}, {len(tools.tools)} tools"


def check_handshake(exe: str) -> bool:
    print("4. MCP handshake over stdio")
    try:
        summary = asyncio.run(asyncio.wait_for(_handshake(exe), timeout=60))
    except Exception as exc:  # pragma: no cover - diagnostic path
        _fail(f"{type(exc).__name__}: {exc}")
        return False
    _ok(summary)
    return True


def check_config() -> bool:
    print("5. .mcp.json in this directory")
    path = ROOT / ".mcp.json"
    if not path.exists():
        print("   none here — fine if you registered the server somewhere else,")
        print("        but Claude Code looks for it in the directory it was started in")
        return True
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        _fail(
            f"invalid JSON: {exc}",
            hint="on Windows, backslashes in the command path must be doubled",
        )
        return False

    servers = config.get("mcpServers", {})
    if not servers:
        _fail("no mcpServers entry")
        return False

    good = True
    for name, entry in servers.items():
        command = entry.get("command", "")
        if Path(command).exists():
            _ok(f"{name} -> {command}")
        else:
            good = False
            _fail(f"{name} -> {command}", hint="that path does not exist on this machine")
    return good


def main() -> int:
    print(f"halflife mcp doctor — {ROOT}\n")
    if not check_import():
        return 1
    exe = check_executable()
    if exe is None:
        return 1
    if not check_starts(exe):
        return 1
    if not check_handshake(exe):
        return 1
    config_ok = check_config()

    print(
        "\nThe server works. If the harness still cannot attach:\n"
        "  - restart it; MCP servers are loaded at startup, not on config change\n"
        "  - check the harness's own MCP log for the reason it rejected the server\n"
        "  - confirm the harness supports local stdio servers rather than only remote URLs"
    )
    return 0 if config_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
