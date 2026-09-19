"""OpenAI implementation of the provider-neutral CMFit LLM interface."""
from __future__ import annotations

import json
import os
import time
from typing import Any

from openai import AsyncOpenAI

from .llm_provider import ChatResult, LLMProvider, ToolExecutor
from .logging_config import get_logger

logger = get_logger('cmfit.openai')


class OpenAIProvider(LLMProvider):
    name = 'openai'

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or os.getenv('CMFIT_OPENAI_MODEL', 'gpt-5.6-luna')
        self.client = AsyncOpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))

    @staticmethod
    def _openai_tools(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for tool in mcp_tools:
            result.append({
                'type': 'function',
                'name': tool['name'],
                'description': tool.get('description') or '',
                'parameters': tool.get('input_schema') or {'type': 'object', 'properties': {}},
                'strict': False,
            })
        return result

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
        openai_tools = self._openai_tools(tools)
        input_items: list[Any] = [
            {'role': item['role'], 'content': item['content']}
            for item in messages
            if item.get('role') in {'user', 'assistant'} and item.get('content')
        ]
        executed: list[dict[str, Any]] = []

        for iteration in range(1, 9):
            started = time.monotonic()
            logger.info(
                '[%s] OpenAI request started | model=%s | iteration=%s | tools=%s | input_items=%s',
                request_id, self.model, iteration, len(openai_tools), len(input_items),
            )

            try:
                response = await self.client.responses.create(
                    model=self.model,
                    instructions=instructions,
                    input=input_items,
                    tools=openai_tools,
                    tool_choice='auto',
                    store=False,
                )
            except Exception as exc:
                logger.exception(
                    '[%s] OpenAI request failed | model=%s | iteration=%s | error_type=%s | elapsed_ms=%d',
                    request_id, self.model, iteration, type(exc).__name__,
                    int((time.monotonic() - started) * 1000),
                )
                raise

            function_calls = [item for item in response.output if item.type == 'function_call']
            logger.info(
                '[%s] OpenAI request completed | model=%s | iteration=%s | output_items=%s | function_calls=%s | elapsed_ms=%d',
                request_id, self.model, iteration, len(response.output), len(function_calls),
                int((time.monotonic() - started) * 1000),
            )

            if not function_calls:
                return ChatResult(
                    text=response.output_text or 'Done.',
                    provider=self.name,
                    model=self.model,
                    tool_calls=executed,
                )

            input_items.extend(response.output)

            for call in function_calls:
                try:
                    arguments = json.loads(call.arguments or '{}')
                except json.JSONDecodeError:
                    arguments = {}
                    logger.warning(
                        '[%s] OpenAI returned invalid JSON tool arguments | tool=%s',
                        request_id, call.name,
                    )

                logger.info('[%s] LLM requested MCP tool | tool=%s', request_id, call.name)
                try:
                    output = await tool_executor(call.name, arguments)
                except Exception as exc:
                    logger.exception(
                        '[%s] Tool execution returned error to LLM | tool=%s | error_type=%s',
                        request_id, call.name, type(exc).__name__,
                    )
                    output = {'error': str(exc)}

                # Keep the existing result contract. Arguments/output are returned to
                # the browser as before, but are intentionally not written to logs.
                executed.append({'name': call.name, 'arguments': arguments, 'output': output})
                input_items.append({
                    'type': 'function_call_output',
                    'call_id': call.call_id,
                    'output': json.dumps(output, default=str),
                })

        logger.warning('[%s] OpenAI tool-call iteration limit reached', request_id)
        return ChatResult(
            text="I couldn't complete that request within the tool-call limit.",
            provider=self.name,
            model=self.model,
            tool_calls=executed,
        )
