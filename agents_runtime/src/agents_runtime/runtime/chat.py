"""Chat orchestrator and streaming helpers."""


import json
from collections.abc import Callable

from agents import Agent, ModelSettings, RunConfig, Runner, function_tool
from agents.extensions.models.litellm_provider import LitellmProvider

from agents_runtime.prompts import load_prompt
from agents_runtime.runtime.context import RuntimeContext
from agents_runtime.runtime.pipeline import run_request


ToolStatusCallback = Callable[[str], None]
TextDeltaCallback = Callable[[str], None]
FinalCallback = Callable[[str], None]
RUN_CONFIG = RunConfig(model_provider=LitellmProvider())


def build_chat_agent(ctx: RuntimeContext, db_key: str) -> Agent:
    """Build the user-facing chat orchestrator agent."""
    @function_tool
    async def run_analytics_pipeline(user_request: str) -> str:
        """Run full analytics pipeline and return formatted output."""
        result = await run_request(ctx, user_request, db_key=db_key, use_narrator=True)
        return result.final_output

    return Agent(
        name="Chat Orchestrator",
        model=ctx.settings.model_general,
        model_settings=ModelSettings(temperature=ctx.settings.default_temperature),
        instructions=load_prompt("chat_orchestrator"),
        tools=[run_analytics_pipeline],
        mcp_servers=[],
    )


async def run_chat_request(ctx: RuntimeContext, user_prompt: str, db_key: str) -> str:
    """Run a single non-streamed chat request."""
    chat_agent = build_chat_agent(ctx, db_key)
    res = await Runner.run(
        chat_agent,
        user_prompt,
        max_turns=ctx.settings.max_turns_chat_orchestrator,
        run_config=RUN_CONFIG,
    )
    out = res.final_output
    if isinstance(out, str):
        return out
    if isinstance(out, dict):
        return json.dumps(out, indent=2)
    return str(out)


def tool_friendly_name(tool_name: str) -> str:
    """Map internal tool names to user-friendly progress text."""
    mapping = {
        "run_analytics_pipeline": "Analyzing your data",
        "run_structured_analysis": "Preparing detailed results",
        "run_analytics_and_export": "Creating your report file",
        "run_chat_backend": "Processing your request",
    }
    return mapping.get(tool_name, "Working on your request")


async def stream_chat_request(
    ctx: RuntimeContext,
    user_prompt: str,
    db_key: str,
    on_status: ToolStatusCallback | None = None,
    on_text_delta: TextDeltaCallback | None = None,
    on_final: FinalCallback | None = None,
) -> str:
    """Stream chat output and optional status updates via callbacks."""
    chat_agent = build_chat_agent(ctx, db_key)
    stream = Runner.run_streamed(
        chat_agent,
        user_prompt,
        max_turns=ctx.settings.max_turns_chat_orchestrator,
        run_config=RUN_CONFIG,
    )

    text_buf = ""
    has_streamed_output = False

    async for ev in stream.stream_events():
        if ev.type == "run_item_stream_event":
            if ev.name == "tool_called":
                raw_item = getattr(ev.item, "raw_item", None)
                if isinstance(raw_item, dict):
                    tool_name = raw_item.get("name")
                else:
                    tool_name = getattr(raw_item, "name", None)
                if on_status:
                    on_status(tool_friendly_name(tool_name or "unknown_tool"))
            elif ev.name == "tool_output" and on_status:
                on_status("Preparing your response")
            elif ev.name == "reasoning_item_created" and on_status:
                on_status("Reasoning")
        elif ev.type == "agent_updated_stream_event" and on_status:
            on_status("Working on the next part")
        elif ev.type == "raw_response_event":
            dt = getattr(ev.data, "type", "")
            if dt == "response.output_text.delta":
                delta = getattr(ev.data, "delta", "")
                if delta:
                    has_streamed_output = True
                    text_buf += delta
                    if on_text_delta:
                        on_text_delta(delta)

    out = stream.final_output_as(str)
    if not has_streamed_output:
        if isinstance(out, str):
            text_buf = out
        elif isinstance(out, dict):
            text_buf = json.dumps(out, indent=2)
        else:
            text_buf = str(out)

    if on_final:
        on_final(text_buf)
    return text_buf
