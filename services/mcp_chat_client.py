"""Thin stdio MCP client used by the CMFit chat agent."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .logging_config import get_logger

logger = get_logger('cmfit.mcp')


class CMFitMCPClient:
    def __init__(self, project_dir: str, request_id: str | None = None):
        self.project_dir = project_dir
        self.request_id = request_id or 'chat-unknown'
        self._stdio_cm = None
        self._session_cm = None
        self.session = None

    async def __aenter__(self):
        python_executable = os.getenv('CMFIT_PYTHON') or sys.executable
        server_path = os.path.join(self.project_dir, 'mcp_server.py')
        logger.info('[%s] MCP server starting | python=%s', self.request_id, python_executable)

        server = StdioServerParameters(
            command=python_executable,
            args=[server_path],
            cwd=self.project_dir,
        )

        try:
            self._stdio_cm = stdio_client(server)
            read, write = await asyncio.wait_for(self._stdio_cm.__aenter__(), timeout=10)
            logger.info('[%s] MCP stdio opened', self.request_id)

            self._session_cm = ClientSession(read, write)
            self.session = await self._session_cm.__aenter__()
            await asyncio.wait_for(self.session.initialize(), timeout=10)
            logger.info('[%s] MCP session initialized', self.request_id)
            return self
        except Exception as exc:
            logger.exception(
                '[%s] MCP startup failed | error_type=%s',
                self.request_id, type(exc).__name__,
            )
            raise

    async def __aexit__(self, exc_type, exc, tb):
        logger.info('[%s] MCP shutdown started', self.request_id)
        cleanup_errors = []

        if self._session_cm:
            try:
                await self._session_cm.__aexit__(exc_type, exc, tb)
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
                logger.exception(
                    '[%s] MCP session cleanup failed | error_type=%s',
                    self.request_id, type(cleanup_exc).__name__,
                )

        if self._stdio_cm:
            try:
                await self._stdio_cm.__aexit__(exc_type, exc, tb)
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
                logger.exception(
                    '[%s] MCP stdio cleanup failed | error_type=%s',
                    self.request_id, type(cleanup_exc).__name__,
                )

        if cleanup_errors:
            logger.warning(
                '[%s] MCP shutdown completed with %s cleanup error(s)',
                self.request_id, len(cleanup_errors),
            )
        else:
            logger.info('[%s] MCP shutdown completed', self.request_id)

        # Do not mask the actual chat/provider/tool result with an MCP cleanup-only
        # exception. Cleanup failures are retained in the persistent log above.
        return False

    async def tools(self) -> list[dict[str, Any]]:
        logger.info('[%s] MCP tool discovery started', self.request_id)
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(self.session.list_tools(), timeout=10)
        except asyncio.TimeoutError as exc:
            logger.exception('[%s] MCP tool discovery timed out after 10 seconds', self.request_id)
            raise RuntimeError('CMFit MCP server timed out while listing tools.') from exc
        except Exception as exc:
            logger.exception(
                '[%s] MCP tool discovery failed | error_type=%s',
                self.request_id, type(exc).__name__,
            )
            raise

        logger.info(
            '[%s] MCP tool discovery completed | count=%s | elapsed_ms=%d',
            self.request_id, len(result.tools), int((time.monotonic() - started) * 1000),
        )
        return [
            {
                'name': tool.name,
                'description': tool.description or '',
                'input_schema': tool.input_schema or {'type': 'object', 'properties': {}},
            }
            for tool in result.tools
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        started = time.monotonic()
        logger.info('[%s] MCP tool call started | tool=%s', self.request_id, name)
        try:
            result = await asyncio.wait_for(self.session.call_tool(name, arguments), timeout=30)
        except asyncio.TimeoutError as exc:
            logger.exception('[%s] MCP tool call timed out | tool=%s', self.request_id, name)
            raise RuntimeError(f"CMFit MCP tool '{name}' timed out.") from exc
        except Exception as exc:
            logger.exception(
                '[%s] MCP tool call failed | tool=%s | error_type=%s',
                self.request_id, name, type(exc).__name__,
            )
            raise

        logger.info(
            '[%s] MCP tool call completed | tool=%s | elapsed_ms=%d',
            self.request_id, name, int((time.monotonic() - started) * 1000),
        )

        structured = getattr(result, 'structuredContent', None)
        if structured is not None:
            return structured

        texts = [item.text for item in result.content if hasattr(item, 'text')]
        if len(texts) == 1:
            try:
                return json.loads(texts[0])
            except (json.JSONDecodeError, TypeError):
                return texts[0]
        return texts
