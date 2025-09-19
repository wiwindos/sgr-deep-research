import logging
import uuid
from typing import Type

from sgr_deep_research.core.agents.sgr_tools_agent import SGRToolCallingResearchAgent
from sgr_deep_research.core.llm import LLMCompletionRequest
from sgr_deep_research.core.tools import BaseTool, ReasoningTool
from sgr_deep_research.settings import get_config

logging.basicConfig(
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s - %(name)s - %(lineno)d - %(levelname)s -  - %(message)s",
    handlers=[logging.StreamHandler()],
)

config = get_config()
logger = logging.getLogger(__name__)


class SGRSOToolCallingResearchAgent(SGRToolCallingResearchAgent):
    """Agent that uses OpenAI native function calling to select and execute
    tools based on SGR like reasoning scheme."""

    def __init__(
        self,
        task: str,
        toolkit: list[Type[BaseTool]] | None = None,
        max_clarifications: int = 3,
        max_searches: int = 4,
        max_iterations: int = 10,
    ):
        super().__init__(
            task=task,
            toolkit=toolkit,
            max_clarifications=max_clarifications,
            max_iterations=max_iterations,
            max_searches=max_searches,
        )
        self.id = f"sgr_so_tool_calling_agent_{uuid.uuid4()}"

    async def _reasoning_phase(self) -> ReasoningTool:
        tool_request = LLMCompletionRequest(
            messages=await self._prepare_context(),
            tools=await self._prepare_tools(),
            tool_choice={"type": "function", "function": {"name": ReasoningTool.tool_name}},
            max_tokens=self.llm_client.default_max_tokens,
            temperature=self.llm_client.default_temperature,
            model=config.llm.resolved_model(config.openai, config.mistral),
        )
        async with self.llm_client.stream_chat_completion(tool_request) as stream:
            async for chunk in stream:
                if chunk.content:
                    self.streaming_generator.add_chunk(chunk.content)
            tool_result = await stream.get_final_response()
        if not tool_result.tool_calls:
            raise ValueError("Reasoning stage did not return tool call")
        if not isinstance(tool_result.tool_calls[0].parsed, ReasoningTool):
            raise ValueError("Unexpected reasoning call payload")

        structured_request = LLMCompletionRequest(
            messages=await self._prepare_context(),
            response_model=ReasoningTool,
            max_tokens=self.llm_client.default_max_tokens,
            temperature=self.llm_client.default_temperature,
            model=config.llm.resolved_model(config.openai, config.mistral),
        )
        async with self.llm_client.stream_chat_completion(structured_request) as stream:
            async for chunk in stream:
                if chunk.content:
                    self.streaming_generator.add_chunk(chunk.content)
            structured_result = await stream.get_final_response()
        reasoning = structured_result.parsed
        if not isinstance(reasoning, ReasoningTool):
            raise ValueError("Structured reasoning response invalid")
        tool_call_result = reasoning(self._context)
        self.conversation.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "type": "function",
                        "id": f"{self._context.iteration}-reasoning",
                        "function": {
                            "name": reasoning.tool_name,
                            "arguments": "{}",
                        },
                    }
                ],
            }
        )
        self.conversation.append(
            {"role": "tool", "content": tool_call_result, "tool_call_id": f"{self._context.iteration}-reasoning"}
        )
        self._log_reasoning(reasoning)
        return reasoning
