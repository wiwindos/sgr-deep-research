import logging
import uuid

from core.models import AgentStatesEnum, ResearchContext
from core.reasoning_schemas import get_system_prompt, ReportCompletion, Clarification, CreateReport
from openai import AsyncOpenAI

from core.tools import NextStepTools
from settings import get_config

# Настройка базового логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Вывод в консоль
    ]
)

config = get_config().app_config
logger = logging.getLogger(__name__)


class SGRAgent:

    def __init__(self):
        self.id = uuid.uuid4()
        self._context = ResearchContext()
        self.openai_client = AsyncOpenAI(base_url=config.openai.base_url, api_key=config.openai.api_key)
        self.state = AgentStatesEnum.INITED

    # ToDo: wip
    # def execute(self, research_request: str):
    #     if not research_request:
    #         raise ValueError("Research request cannot be empty")
    #     while True:
    #         execute_research_task()

    async def _prepare_context(self, task: str) -> str:
        context_msg = ""
        if self._context.clarification_used:
            context_msg = ("IMPORTANT: Clarification already used. "
                           "Do not request clarification again - proceed with available information.")

        # ToDo: maybe this part of logic should be implemented in code?
        # ToDo: is it really necessary to attach the original request in every subsequent message?
        user_request_info = f"\nORIGINAL USER REQUEST: '{task}'\n(Use this for language consistency in reports)"
        search_count_info = f"\nSEARCHES COMPLETED: {len(self._context.searches)} (MAX 3-4 searches before creating report)"
        context_msg = (context_msg + "\n" + user_request_info + search_count_info).strip()

        # Add available sources information
        if self._context.sources:
            sources_info = ("\nAVAILABLE SOURCES FOR CITATIONS:\n" +
                            "\n".join([str(source) for source in self._context.sources.values()]) +
                            "\nUSE THESE EXACT NUMBERS [1], [2], [3] etc. in your report citations."
                            )
            context_msg = context_msg + "\n" + sources_info
        return context_msg

    async def provide_clarification(self, clarifications: str):
        """Receive clarification from external source (e.g. user input)"""
        self._context.clarifications = clarifications
        self._context.clarification_used = True
        self._context.clarification_received.set()
        self.state = AgentStatesEnum.RESEARCHING
        logger.info(f"✅ Clarification received: {clarifications[:300]}...")

    async def _handle_research_task(self, task: str):
        """Execute research task using SGR"""

        system_prompt = get_system_prompt(task)
        conversation = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task}
        ]
        # Execute reasoning steps
        for i in range(config.execution.max_steps):
            step_id = f"step-{i + 1}"
            logger.info(f"agent {self.id} Step {step_id}")

            # Add context about clarification usage and available sources
            context_msg = await self._prepare_context(task)
            # ToDo: role should be system or assistant?
            conversation.append({"role": "system", "content": context_msg})
            logger.info(f"New context for LLM: {context_msg}")
            try:
                completion = await self.openai_client.beta.chat.completions.parse(
                    model=config.openai.model,
                    response_format=NextStepTools,
                    messages=conversation,
                    max_tokens=config.openai.max_tokens,
                    temperature=config.openai.temperature,
                )

                result: NextStepTools = completion.choices[0].message.parsed

                if result is None:
                    logger.error(f"Failed to parse LLM response: {completion}")
                    break

                # Debug: Log ALL NextStep fields
                logger.info("🤖 LLM RESPONSE DEBUG:")
                logger.info(f"   🧠 Reasoning Steps: {result.reasoning_steps}")
                logger.info(f"   📊 Current Situation: '{result.current_situation[:100]}...'")
                logger.info(f"   📋 Plan Status: '{result.plan_status[:100]}...'")
                logger.info(f"   🔍 Searches Done: {result.searches_done}")
                logger.info(f"   ✅ Enough Data: {result.enough_data}")
                logger.info(f"   📝 Remaining Steps: {result.remaining_steps}")
                logger.info(f"   🏁 Task Completed: {result.task_completed}")
                logger.info(f"   🔧 Tool: {result.function.tool}")
            except Exception as e:
                logger.error(f"❌ LLM request error: {str(e)}")
                break

            tool_call_result = result.function(self._context)

            # ToDo: need refactoring, should be the better way. Something like state machine?
            if result.task_completed or isinstance(result.function, ReportCompletion):
                logger.info("✅ Research task completed.")
                break

            # Check for clarification cycling
            # ToDo: looks like a hack. Clarification option should be excluded from model context on previous steps
            if isinstance(result.function, Clarification):
                if self._context.clarification_used:
                    logger.warning("❌ Clarification cycling detected - skipping clarification")
                    conversation.append({
                        "role": "user",
                        "content": "ANTI-CYCLING: Clarification already used. Continue with generate_plan based on available information."
                    })
                    continue
                self.state = AgentStatesEnum.WAITING_FOR_CLARIFICATION
                await self._context.clarification_received.wait()
                task = f"Original request: '{task}'\nClarification: {self._context.clarifications}\n\nProceed with research based on clarification."
                continue

            # Display current step
            next_step = result.remaining_steps[0] if result.remaining_steps else "Completing"
            logger.info(f"➡️\n"
                        f"   Next Step: {next_step} using {result.function.tool}\n"
                        f"   Reasoning: {result.function.reasoning[:500]}...\n"
                        f"   Tool: {result.function.tool}")

            conversation.append({
                "role": "assistant",
                "content": next_step,
                "tool_calls": [{
                    "type": "function",
                    "id": str(step_id),
                    "function": {
                        "name": result.function.tool,
                        "arguments": result.function.model_dump_json()
                    }
                }]
            })

            # Add result to conversation - format search results better
            # ToDo: wtf is this? need refactoring
            conversation.append({"role": "tool", "content": tool_call_result, "tool_call_id": step_id})

            print(f"  Result: {tool_call_result[:100]}..." if len(tool_call_result) > 100 else f"  Result: {tool_call_result}")

            # Auto-complete after report creation
            if isinstance(result.function, CreateReport):
                print("\n✅ [bold green]Auto-completing after report creation[/bold green]")
                break

async def main():
    agent = SGRAgent()
    research_request = "Исследовать актуальные цены на BMW X6 2025 года в России"
    await agent._handle_research_task(research_request)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())