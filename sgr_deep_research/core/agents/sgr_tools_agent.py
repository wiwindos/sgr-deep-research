import logging
import uuid
from typing import Literal, Type

from openai import pydantic_function_tool
from openai.types.chat import ChatCompletionFunctionToolParam

from sgr_deep_research.core.agents.sgr_agent import SGRResearchAgent
from sgr_deep_research.core.tools import (
    AgentCompletionTool,
    BaseTool,
    ClarificationTool,
    CreateReportTool,
    ReasoningTool,
    WebSearchTool,
    research_agent_tools,
    system_agent_tools,
)
logging.basicConfig(
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s - %(name)s - %(lineno)d - %(levelname)s -  - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


class SGRToolCallingResearchAgent(SGRResearchAgent):
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
        self.id = f"sgr_tool_calling_agent_{uuid.uuid4()}"
        self.toolkit = [*system_agent_tools, *research_agent_tools, *(toolkit if toolkit else [])]
        self.tool_choice: Literal["required"] = "required"
        self._tool_name_mapping: dict[str, Type[BaseTool]] = {
            tool.tool_name: tool for tool in self.toolkit
        }

    async def _prepare_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """Prepare available tools for current agent state and progress."""
        tools = set(self.toolkit)
        if self._context.iteration >= self.max_iterations:
            tools = [
                ReasoningTool,
                CreateReportTool,
                AgentCompletionTool,
            ]
        if self._context.clarifications_used >= self.max_clarifications:
            tools -= {
                ClarificationTool,
            }
        if self._context.searches_used >= self.max_searches:
            tools -= {
                WebSearchTool,
            }
        tool_list = list(tools)
        self._tool_name_mapping = {tool.tool_name: tool for tool in tool_list}
        return [pydantic_function_tool(tool, name=tool.tool_name, description=tool.description) for tool in tool_list]

    async def _reasoning_phase(self) -> ReasoningTool:
        tools = await self._prepare_tools()
        response = await self._chat_completion(
            messages=await self._prepare_context(),
            tools=tools,
            tool_choice={"type": "function", "function": {"name": ReasoningTool.tool_name}},
            tool_classes=self._tool_name_mapping,
        )
        if not response.tool_calls:
            raise ValueError("Model response did not include a reasoning tool call")
        reasoning = response.tool_calls[0].parsed_arguments
        if not isinstance(reasoning, ReasoningTool):
            raise ValueError("Invalid reasoning tool returned by model")
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
                            "arguments": reasoning.model_dump_json(),
                        },
                    }
                ],
            }
        )
        tool_call_result = reasoning(self._context)
        self.conversation.append(
            {"role": "tool", "content": tool_call_result, "tool_call_id": f"{self._context.iteration}-reasoning"}
        )
        self._log_reasoning(reasoning)
        return reasoning

    async def _select_action_phase(self, reasoning: ReasoningTool) -> BaseTool:
        tools = await self._prepare_tools()
        response = await self._chat_completion(
            messages=await self._prepare_context(),
            tools=tools,
            tool_choice=self.tool_choice,
            tool_classes=self._tool_name_mapping,
        )
        if not response.tool_calls:
            raise ValueError("Model response did not include a tool selection")
        tool = response.tool_calls[0].parsed_arguments

        if not isinstance(tool, BaseTool):
            raise ValueError("Selected tool is not a valid BaseTool instance")
        self.conversation.append(
            {
                "role": "assistant",
                "content": reasoning.remaining_steps[0] if reasoning.remaining_steps else "Completing",
                "tool_calls": [
                    {
                        "type": "function",
                        "id": f"{self._context.iteration}-action",
                        "function": {
                            "name": tool.tool_name,
                            "arguments": tool.model_dump_json(),
                        },
                    }
                ],
            }
        )
        self.streaming_generator.add_tool_call(
            f"{self._context.iteration}-action", tool.tool_name, tool.model_dump_json()
        )
        return tool
