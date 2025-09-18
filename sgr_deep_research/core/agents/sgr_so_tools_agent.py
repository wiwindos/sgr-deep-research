import logging
import uuid
from typing import Type

from sgr_deep_research.core.agents.sgr_tools_agent import SGRToolCallingResearchAgent
from sgr_deep_research.core.tools import BaseTool, ReasoningTool
logging.basicConfig(
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s - %(name)s - %(lineno)d - %(levelname)s -  - %(message)s",
    handlers=[logging.StreamHandler()],
)

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
        tools = await self._prepare_tools()
        first_response = await self._chat_completion(
            messages=await self._prepare_context(),
            tools=tools,
            tool_choice={"type": "function", "function": {"name": ReasoningTool.tool_name}},
            tool_classes=self._tool_name_mapping,
        )
        if first_response.tool_calls:
            reasoning_tool = first_response.tool_calls[0].parsed_arguments
            if reasoning_tool is not None and not isinstance(reasoning_tool, ReasoningTool):
                raise ValueError("Invalid reasoning tool returned by model")

        structured_response = await self._chat_completion(
            messages=await self._prepare_context(),
            response_format=ReasoningTool,
        )
        reasoning = structured_response.parsed
        if not isinstance(reasoning, ReasoningTool):
            raise ValueError("Structured reasoning response does not match expected schema")
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
