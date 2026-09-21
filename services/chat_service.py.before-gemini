"""CMFit chat orchestration independent of any one LLM provider."""
from __future__ import annotations

import os
import time
from typing import Any

from .logging_config import get_logger
from .mcp_chat_client import CMFitMCPClient
from .openai_provider import OpenAIProvider

logger = get_logger('cmfit.chat')

BASE_INSTRUCTIONS = """You are the CMFit assistant embedded in the user's fitness application.
Use CMFit tools for facts about the user's exercises, workouts, history, fitness tests, and for requested actions.
Never invent IDs, workout history, logged values, or tool results.
For write tools, act only when the user clearly asks to create, change, start, log, save, remove, reorder, or finish something.
After a successful write, briefly confirm exactly what was changed.
If a tool returns an error, explain the error and do not claim success.
Keep responses concise and mobile-friendly.

WORKOUT SET CONTEXT:
When context mode is workout_set, the supplied workout_log_id and workout_exercise_id identify the exact active set row the user is speaking about. Do not ask the user to identify the exercise again.
If the user gives set performance, call log_set using those context IDs. If the same command includes rest duration and/or starting/ending heart rate, first log_set, obtain the returned set id, then call save_rest with that set id.
Examples: '10 reps 95 pounds starting heart rate 140 ending heart rate 100 with 60 seconds rest' means reps=10, weight=95, starting_heart_rate=140, ending_heart_rate=100, rest_seconds=60.
For duration-based rows, map spoken duration to duration rather than reps.
"""


def _provider():
    provider_name = os.getenv('CMFIT_LLM_PROVIDER', 'openai').strip().lower()
    if provider_name == 'openai':
        return OpenAIProvider()
    raise ValueError(f'Unsupported CMFIT_LLM_PROVIDER: {provider_name}')


def _context_instructions(context: dict[str, Any] | None) -> str:
    context = context or {}
    if context.get('mode') != 'workout_set':
        return '\nCurrent UI context: global CMFit chat.'
    return (
        '\nCurrent UI context: workout_set'
        f"\nworkout_log_id={context.get('workout_log_id')}"
        f"\nworkout_exercise_id={context.get('workout_exercise_id')}"
        f"\nexercise_name={context.get('exercise_name') or ''}"
        f"\nset_number={context.get('set_number') or ''}"
        f"\ncategory={context.get('category') or ''}"
    )


async def run_chat(
    project_dir: str,
    messages: list[dict[str, str]],
    context=None,
    request_id: str | None = None,
) -> dict[str, Any]:
    request_id = request_id or 'chat-unknown'
    started = time.monotonic()
    mode = (context or {}).get('mode', 'global')

    logger.info(
        '[%s] Chat orchestration started | mode=%s | messages=%s',
        request_id, mode, len(messages),
    )

    try:
        provider = _provider()
        logger.info(
            '[%s] LLM provider initialized | provider=%s | model=%s',
            request_id, provider.name, getattr(provider, 'model', 'unknown'),
        )

        async with CMFitMCPClient(project_dir, request_id=request_id) as mcp:
            tools = await mcp.tools()
            logger.info('[%s] MCP tools ready | count=%s', request_id, len(tools))

            result = await provider.chat(
                messages=messages,
                instructions=BASE_INSTRUCTIONS + _context_instructions(context),
                tools=tools,
                tool_executor=mcp.call,
                request_id=request_id,
            )

        logger.info(
            '[%s] Chat orchestration completed | provider=%s | model=%s | tool_calls=%s | elapsed_ms=%d',
            request_id, result.provider, result.model, len(result.tool_calls),
            int((time.monotonic() - started) * 1000),
        )
        return {
            'message': result.text,
            'provider': result.provider,
            'model': result.model,
            'tool_calls': result.tool_calls,
        }
    except Exception as exc:
        logger.exception(
            '[%s] Chat orchestration failed | error_type=%s | elapsed_ms=%d',
            request_id, type(exc).__name__, int((time.monotonic() - started) * 1000),
        )
        raise
