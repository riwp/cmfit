"""Gemini implementation of the provider-neutral CMFit LLM interface."""
from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

from google import genai
from google.genai import types

from .llm_provider import ChatResult, LLMProvider, ToolExecutor
from .logging_config import get_logger

logger = get_logger('cmfit.gemini')


class GeminiProvider(LLMProvider):
    name = 'gemini'

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv('CMFIT_GEMINI_MODEL', 'gemini-3-flash-preview')
        resolved_key = api_key or os.getenv('GEMINI_API_KEY')
        if not resolved_key:
            raise ValueError('GEMINI_API_KEY is not configured.')
        self.client = genai.Client(api_key=resolved_key)

    @staticmethod
    def _gemini_tools(mcp_tools: list[dict[str, Any]]) -> list[types.Tool]:
        declarations = []
        for tool in mcp_tools:
            declarations.append(
                types.FunctionDeclaration(
                    name=tool['name'],
                    description=tool.get('description') or '',
                    parameters=tool.get('input_schema')
                    or {'type': 'object', 'properties': {}},
                )
            )
        return [types.Tool(function_declarations=declarations)] if declarations else []

    @staticmethod
    def _contents(messages: list[dict[str, str]]) -> list[types.Content]:
        contents: list[types.Content] = []
        for item in messages:
            role = item.get('role')
            content = item.get('content')
            if role not in {'user', 'assistant'} or not content:
                continue
            contents.append(
                types.Content(
                    role='model' if role == 'assistant' else 'user',
                    parts=[types.Part.from_text(text=content)],
                )
            )
        return contents

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        instructions: str,
        tools: list[dict[str, Any]],
        tool_executor: ToolExecutor,
        request_id: str | None = None,
    ) -> ChatResult:
        request_id = request_id or 'chat-unknown'
        gemini_tools = self._gemini_tools(tools)
        contents = self._contents(messages)
        executed: list[dict[str, Any]] = []

        config = types.GenerateContentConfig(
            system_instruction=instructions,
            tools=gemini_tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        for iteration in range(1, 9):
            started = time.monotonic()
            logger.info(
                '[%s] Gemini request started | model=%s | iteration=%s | tools=%s | contents=%s',
                request_id, self.model, iteration, len(tools), len(contents),
            )

            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:
                logger.exception(
                    '[%s] Gemini request failed | model=%s | iteration=%s | error_type=%s | elapsed_ms=%d',
                    request_id, self.model, iteration, type(exc).__name__,
                    int((time.monotonic() - started) * 1000),
                )
                raise

            function_calls = list(response.function_calls or [])
            logger.info(
                '[%s] Gemini request completed | model=%s | iteration=%s | function_calls=%s | elapsed_ms=%d',
                request_id, self.model, iteration, len(function_calls),
                int((time.monotonic() - started) * 1000),
            )

            if not function_calls:
                return ChatResult(
                    text=(response.text or 'Done.').strip(),
                    provider=self.name,
                    model=self.model,
                    tool_calls=executed,
                )

            # Preserve Gemini's complete model response, including function-call
            # parts and any Gemini 3 thought signatures needed on the next turn.
            if not response.candidates or not response.candidates[0].content:
                raise RuntimeError('Gemini returned function calls without model content.')
            contents.append(response.candidates[0].content)

            function_response_parts: list[types.Part] = []
            for call in function_calls:
                arguments = dict(call.args or {})
                logger.info('[%s] LLM requested MCP tool | tool=%s', request_id, call.name)

                try:
                    output = await tool_executor(call.name, arguments)
                except Exception as exc:
                    logger.exception(
                        '[%s] Tool execution returned error to LLM | tool=%s | error_type=%s',
                        request_id, call.name, type(exc).__name__,
                    )
                    output = {'error': str(exc)}

                executed.append({
                    'name': call.name,
                    'arguments': arguments,
                    'output': output,
                })

                # FunctionResponse.response must be an object. Wrapping the MCP
                # result also handles scalar/list/string tool results consistently.
                function_response_parts.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response={'result': output},
                    )
                )

            contents.append(
                types.Content(role='user', parts=function_response_parts)
            )

        logger.warning('[%s] Gemini tool-call iteration limit reached', request_id)
        return ChatResult(
            text="I couldn't complete that request within the tool-call limit.",
            provider=self.name,
            model=self.model,
            tool_calls=executed,
        )
