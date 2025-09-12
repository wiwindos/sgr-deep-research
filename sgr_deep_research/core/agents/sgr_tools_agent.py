import json
import logging
import traceback
import uuid
from datetime import datetime
from typing import Literal, Type

import httpx
from openai import AsyncOpenAI, pydantic_function_tool
from openai.types.chat import ChatCompletionFunctionToolParam

from sgr_deep_research.core.models import AgentStatesEnum, ResearchContext
from sgr_deep_research.core.prompts import PromptLoader
from sgr_deep_research.core.stream import OpenAIStreamingGenerator
from sgr_deep_research.core.tools import (
    ClarificationTool,
    CompletionTool,
    NextStepToolStub,
    WebSearchTool,
)
from sgr_deep_research.core.tools.base import BaseTool, CreateReportTool, ReasoningTool, system_agent_tools
from sgr_deep_research.core.tools.research import research_agent_tools
from sgr_deep_research.settings import get_config

logging.basicConfig(
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s - %(name)s - %(lineno)d - %(levelname)s -  - %(message)s",
    handlers=[logging.StreamHandler()],
)

config = get_config()
logger = logging.getLogger(__name__)


class SGRToolCallingResearchAgent:
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
        self.id = f"sgr_tool_calling_agent_{uuid.uuid4()}"
        self.task = task
        self.toolkit = [*system_agent_tools, *research_agent_tools, ReasoningTool, *(toolkit if toolkit else [])]

        self._context = ResearchContext()
        self.conversation = []
        self.log = []

        self.max_clarifications = max_clarifications
        self.max_searches = max_searches
        self.max_iterations = max_iterations
        # Initialize OpenAI client with optional proxy support
        client_kwargs = {"base_url": config.openai.base_url, "api_key": config.openai.api_key}

        # Add proxy if configured and not empty
        if config.openai.proxy.strip():
            client_kwargs["http_client"] = httpx.AsyncClient(proxy=config.openai.proxy)

        self.openai_client = AsyncOpenAI(**client_kwargs)
        self.streaming_generator = OpenAIStreamingGenerator(model=self.id)
        self.tool_choice: Literal["required"] = "required"

    def _prepare_tools(self) -> list[ChatCompletionFunctionToolParam]:
        """Prepare tool classes with current context limits."""
        tools = set(self.toolkit)
        if self._context.iteration >= self.max_iterations:
            tools = [
                CreateReportTool,
                CompletionTool,
            ]
        if self._context.clarifications_used >= self.max_clarifications:
            tools -= {
                ClarificationTool,
            }
        if self._context.searches_used >= self.max_searches:
            tools -= {
                WebSearchTool,
            }
        return [pydantic_function_tool(tool, name=tool.tool_name, description=tool.description) for tool in tools]

    def _prepare_context(self) -> list[dict]:
        """Prepare conversation context with system prompt and current
        state."""
        system_prompt = PromptLoader.get_system_prompt(
            user_request=self.task, sources=list(self._context.sources.values())
        )
        conversation = [{"role": "system", "content": system_prompt}]
        conversation.extend(self.conversation)
        return conversation

    async def _openai_streaming_request(self) -> NextStepToolStub | None:
        async with self.openai_client.chat.completions.stream(
            model=config.openai.model,
            messages=self._prepare_context(),
            max_tokens=config.openai.max_tokens,
            temperature=config.openai.temperature,
            tools=self._prepare_tools(),
            tool_choice={"type": "function", "function": {"name": ReasoningTool.tool_name}},
        ) as stream:
            async for event in stream:
                # print(event)
                if event.type == "chunk":
                    content = event.chunk.choices[0].delta.content
                    self.streaming_generator.add_chunk(content)
            reasoning: ReasoningTool = (
                (await stream.get_final_completion()).choices[0].message.tool_calls[0].function.parsed_arguments
            )  # noqa
        tool_call_result = reasoning(self._context)
        self._log_reasoning(reasoning)
        self.conversation.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "type": "function",
                        "id": str(self._context.iteration),
                        "function": {
                            "name": reasoning.tool_name,
                            "arguments": reasoning.model_dump_json(),
                        },
                    }
                ],
            }
        )
        self.conversation.append(
            {"role": "tool", "content": tool_call_result, "tool_call_id": str(self._context.iteration)}
        )

        async with self.openai_client.chat.completions.stream(
            model=config.openai.model,
            messages=self._prepare_context(),
            max_tokens=config.openai.max_tokens,
            temperature=config.openai.temperature,
            tools=self._prepare_tools(),
            tool_choice=self.tool_choice,
        ) as stream:
            async for event in stream:
                # print(event)
                if event.type == "chunk":
                    content = event.chunk.choices[0].delta.content
                    self.streaming_generator.add_chunk(content)
            return (await stream.get_final_completion()).choices[0].message.tool_calls[0].function.parsed_arguments

    async def provide_clarification(self, clarifications: str):
        """Receive clarification from external source (e.g. user input)"""
        self.conversation.append({"role": "user", "content": f"CLARIFICATIONS: {clarifications}"})
        self._context.clarifications_used += 1
        self._context.clarification_received.set()
        self._context.state = AgentStatesEnum.RESEARCHING
        logger.info(f"✅ Clarification received: {clarifications[:300]}...")

    def _log_reasoning(self, result: ReasoningTool) -> None:
        next_step = result.remaining_steps[0] if result.remaining_steps else "Completing"
        sources = "\n         ".join([str(source) for source in self._context.sources.values()])
        logger.info(
            f"""
###############################################
🤖 LLM RESPONSE DEBUG:
   🧠 Reasoning Steps: {result.reasoning_steps}
   📊 Current Situation: '{result.current_situation[:100]}...'
   📋 Plan Status: '{result.plan_status[:100]}...'
   🔍 Searches Done: {self._context.searches_used}
   🔍 Clarifications Done: {self._context.clarifications_used}
   🔍  Sources:
{sources}
   ✅ Enough Data: {result.enough_data}
   📝 Remaining Steps: {result.remaining_steps}
   🏁 Task Completed: {result.task_completed}
   ➡️ Next Step: {next_step}
###############################################"""
        )
        self.log.append(
            {
                "step_number": self._context.iteration,
                "timestamp": datetime.now().isoformat(),
                "step_type": "reasoning",
                "agent_reasoning": result.model_dump(),
            }
        )

    def _log_tool_execution(self, tool: BaseTool, result: str):
        logger.info(
            f"🛠️  Tool Execution Result:\n"
            f"   🔧 Tool: {tool.tool_name}\n"
            f"   📄 Result Preview: '{result[:1000]}...'\n"
        )
        self.log.append(
            {
                "step_number": self._context.iteration,
                "timestamp": datetime.now().isoformat(),
                "step_type": "tool_execution",
                "tool_name": tool.tool_name,
                "agent_tool_execution": tool.model_dump(),
                "agent_tool_execution_result": result,
            }
        )

    def _save_agent_log(self):
        agent_log = {
            "id": self.id,
            "task": self.task,
            "context": self._context.agent_state(),
            "log": self.log,
        }
        json.dump(agent_log, open(f"{self.id}-log.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    async def execute(
        self,
    ):
        """Execute research task using SGR."""
        self.conversation.extend(
            [
                {
                    "role": "user",
                    "content": f"\nORIGINAL USER REQUEST: '{self.task}'\n"
                    f"(Use this for language consistency in reports)",
                }
            ]
        )
        # Execute reasoning steps
        try:
            while self._context.state not in AgentStatesEnum.FINISH_STATES:
                self._context.iteration += 1
                step_id = f"step-{self._context.iteration}"
                logger.info(f"agent {self.id} Step {step_id} started")

                result: BaseTool = await self._openai_streaming_request()
                self.conversation.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "type": "function",
                                "id": str(self._context.iteration),
                                "function": {
                                    "name": result.tool_name,
                                    "arguments": result.model_dump_json(),
                                },
                            }
                        ],
                    }
                )
                self.streaming_generator.add_tool_call(str(step_id), result.tool_name, result.model_dump_json())

                tool_call_result = result(self._context)  # noqa
                self._log_tool_execution(result, tool_call_result)

                self.streaming_generator.add_chunk(f"{tool_call_result}\n")
                self.conversation.append(
                    {"role": "tool", "content": tool_call_result, "tool_call_id": str(self._context.iteration)}
                )

                if isinstance(result, ClarificationTool):
                    logger.info("\n⏸️  Research paused - please answer questions")
                    logger.info(tool_call_result)
                    self._context.state = AgentStatesEnum.WAITING_FOR_CLARIFICATION
                    self._context.clarification_received.clear()
                    await self._context.clarification_received.wait()
                    continue

        except Exception as e:
            logger.error(f"❌ Agent execution error: {str(e)}")
            self._context.state = AgentStatesEnum.FAILED
            traceback.print_exc()
        finally:
            self.streaming_generator.finish()
            self._save_agent_log()
