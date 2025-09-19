import logging
import uuid
from typing import Type

from sgr_deep_research.core.agents.base_agent import BaseAgent
from sgr_deep_research.core.llm import LLMCompletionRequest
from sgr_deep_research.core.tools import (
    AgentCompletionTool,
    BaseTool,
    ClarificationTool,
    CreateReportTool,
    NextStepToolsBuilder,
    NextStepToolStub,
    ReasoningTool,
    WebSearchTool,
    research_agent_tools,
    system_agent_tools,
)
from sgr_deep_research.settings import get_config

logging.basicConfig(
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s - %(name)s - %(lineno)d - %(levelname)s -  - %(message)s",
    handlers=[logging.StreamHandler()],
)

config = get_config()
logger = logging.getLogger(__name__)


class SGRResearchAgent(BaseAgent):
    """Agent for deep research tasks using SGR framework."""

    def __init__(
        self,
        task: str,
        toolkit: list[Type[BaseTool]] | None = None,
        max_clarifications: int = 3,
        max_iterations: int = 10,
        max_searches: int = 4,
    ):
        super().__init__(
            task=task,
            toolkit=toolkit,
            max_clarifications=max_clarifications,
            max_iterations=max_iterations,
        )

        self.id = f"sgr_agent_{uuid.uuid4()}"

        self.toolkit = [
            *system_agent_tools,
            *research_agent_tools,
            *(toolkit or []),
        ]
        self.toolkit.remove(ReasoningTool)  # we use our own reasoning scheme
        self.max_searches = max_searches

    async def _prepare_tools(self) -> Type[NextStepToolStub]:
        """Prepare tool classes with current context limits."""
        tools = set(self.toolkit)
        if self._context.iteration >= self.max_iterations:
            tools = {
                CreateReportTool,
                AgentCompletionTool,
            }
        if self._context.clarifications_used >= self.max_clarifications:
            tools -= {
                ClarificationTool,
            }
        if self._context.searches_used >= self.max_searches:
            tools -= {
                WebSearchTool,
            }
        return NextStepToolsBuilder.build_NextStepTools(list(tools))

    async def _reasoning_phase(self) -> NextStepToolStub:
        response_format = await self._prepare_tools()
        request = LLMCompletionRequest(
            messages=await self._prepare_context(),
            response_model=response_format,
            max_tokens=self.llm_client.default_max_tokens,
            temperature=self.llm_client.default_temperature,
            model=config.llm.resolved_model(config.openai, config.mistral),
        )
        async with self.llm_client.stream_chat_completion(request) as stream:
            async for chunk in stream:
                if chunk.content:
                    self.streaming_generator.add_chunk(chunk.content)
            result = await stream.get_final_response()
        reasoning = result.parsed
        if reasoning is None:
            raise ValueError("Structured reasoning response is empty")
        # we are not fully sure if it should be in conversation or not. Looks like not necessary data
        # self.conversation.append({"role": "assistant", "content": reasoning.model_dump_json(exclude={"function"})})
        self._log_reasoning(reasoning)
        return reasoning

    async def _select_action_phase(self, reasoning: NextStepToolStub) -> BaseTool:
        tool = reasoning.function
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

    async def _action_phase(self, tool: BaseTool) -> str:
        result = tool(self._context)
        self.conversation.append(
            {"role": "tool", "content": result, "tool_call_id": f"{self._context.iteration}-action"}
        )
        self.streaming_generator.add_chunk(f"{result}\n")
        self._log_tool_execution(tool, result)
        return result
