import uuid
from typing import Literal, Type

from sgr_deep_research.core.agents.sgr_tools_agent import SGRToolCallingResearchAgent
from sgr_deep_research.core.tools.base import BaseTool


class SGRAutoToolCallingResearchAgent(SGRToolCallingResearchAgent):
    """SGR Tool Calling Research Agent variation for benchmark with automatic tool selection"""

    def __init__(
        self,
        task: str,
        toolkit: list[Type[BaseTool]] | None = None,
        max_clarifications: int = 3,
        max_searches: int = 4,
        max_iterations: int = 10,
    ):
        super().__init__(task, toolkit, max_clarifications, max_searches, max_iterations)
        self.id = f"sgr_auto_tool_calling_agent_{uuid.uuid4()}"
        self.tool_choice: Literal["auto"] = "auto"


async def main():
    # agent = SGRToolCallingResearchAgent(task="Research the current state of Tesla's Full Self-Driving technology in 2025. I need to understand if Tesla has achieved Level 5 autonomous driving as Elon Musk promised it would be ready by 2024, and whether regulatory approval has been granted worldwide.")
    agent = SGRToolCallingResearchAgent(task="Сравни цену на биткоин за 2023 и 2024 год")
    await agent.execute()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
