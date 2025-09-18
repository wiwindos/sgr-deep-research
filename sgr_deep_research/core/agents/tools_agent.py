import logging
import uuid
from typing import Literal, Type

from openai import pydantic_function_tool
from openai.types.chat import ChatCompletionFunctionToolParam

from sgr_deep_research.core.agents.base_agent import BaseAgent
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


class ToolCallingResearchAgent(BaseAgent):
    """Tool Calling Research Agent relying entirely on LLM native function
    calling."""

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
        )
        self.id = f"tool_calling_agent_{uuid.uuid4()}"

        self.toolkit = [*system_agent_tools, *research_agent_tools, *(toolkit if toolkit else [])]
        self.toolkit.remove(ReasoningTool)  # LLM will do the reasoning internally

        self.max_searches = max_searches
        self.tool_choice: Literal["required"] = "required"
        self._tool_name_mapping: dict[str, Type[BaseTool]] = {
            tool.tool_name: tool for tool in self.toolkit
        }

    async def _prepare_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """Prepare tool classes with current context limits."""
        tools = set(self.toolkit)
        if self._context.iteration >= self.max_iterations:
            tools = [
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

    async def _reasoning_phase(self) -> None:
        """No explicit reasoning phase, reasoning is done internally by LLM."""
        return None

    async def _select_action_phase(self, reasoning=None) -> BaseTool:
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
                "content": None,
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

    async def _action_phase(self, tool: BaseTool) -> str:
        result = tool(self._context)
        self.conversation.append(
            {"role": "tool", "content": result, "tool_call_id": f"{self._context.iteration}-action"}
        )
        self.streaming_generator.add_chunk(f"{result}\n")
        self._log_tool_execution(tool, result)
        return result
