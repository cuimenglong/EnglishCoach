import json
from dataclasses import dataclass, field
from typing import AsyncGenerator, Callable

from openai import AsyncOpenAI


@dataclass
class TextChunk:
    content: str


@dataclass
class FunctionCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Done:
    pass


@dataclass
class Error:
    message: str


Event = TextChunk | FunctionCall | Done | Error


class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str, temperature: float = 0.7):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature

    async def chat(self, messages: list, tools: list | None = None) -> tuple[str, list[dict]]:
        """Non-streaming call. Returns (content, tool_calls_list).

        tool_calls_list contains dicts with keys: id, name, arguments (dict).
        """
        kwargs = dict(model=self.model, messages=messages, temperature=self.temperature)
        if tools:
            kwargs["tools"] = tools

        response = await self.client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        content = msg.content or ""
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                })
        return content, tool_calls

    async def chat_stream(self, messages: list, tools: list | None = None) -> AsyncGenerator[Event, None]:
        """Streaming call. Yields TextChunk, FunctionCall, Done, or Error events."""
        try:
            kwargs = dict(model=self.model, messages=messages, temperature=self.temperature, stream=True)
            if tools:
                kwargs["tools"] = tools

            stream = await self.client.chat.completions.create(**kwargs)

            tool_calls_acc: dict[int, dict] = {}
            full_content = ""

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                if delta.content:
                    full_content += delta.content
                    yield TextChunk(delta.content)

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc.id:
                            tool_calls_acc[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_acc[idx]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls_acc[idx]["arguments"] += tc.function.arguments

                if finish_reason == "tool_calls":
                    for idx, call_data in sorted(tool_calls_acc.items()):
                        try:
                            args = json.loads(call_data["arguments"])
                        except json.JSONDecodeError:
                            args = {}
                        yield FunctionCall(
                            id=call_data["id"],
                            name=call_data["name"],
                            arguments=args,
                        )
                    return

                if finish_reason == "stop":
                    yield Done()
                    return

            yield Done()

        except Exception as e:
            yield Error(str(e))
