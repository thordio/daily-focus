#!/usr/bin/env python3
"""Local smoke check for Horizon MCP integration."""

from __future__ import annotations

import asyncio
import json

from src.mcp.horizon_adapter import resolve_horizon_path
from src.mcp.server import hz_get_metrics
from src.mcp.service import HorizonPipelineService


async def _main() -> None:
    horizon_path = resolve_horizon_path()
    service = HorizonPipelineService()
    validation = await service.validate_config(
        horizon_path=str(horizon_path),
        check_env=False,
    )
    metrics = hz_get_metrics()

    payload = {
        "ok": True,
        "horizon_path": str(horizon_path),
        "config_path": validation["config_path"],
        "enabled_sources": validation["enabled_sources"],
        "languages": validation["ai"]["languages"],
        "metrics_ok": metrics["ok"],
        "metrics_tool": metrics["tool"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
