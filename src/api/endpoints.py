

import asyncio
import logging
from typing import Dict
from uuid import UUID
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from api.models import ChatCompletionRequest, HealthResponse, AgentStateResponse, AgentListResponse, AgentListItem
from core.agent import SGRResearchAgent

logger = logging.getLogger(__name__)

app = FastAPI(title="SGR Deep Research API", version="1.0.0")

# In-memory хранилище агентов
agents_storage: Dict[UUID, SGRResearchAgent] = {}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@app.get("/agents/{agent_id}/state", response_model=AgentStateResponse)
async def get_agent_state(agent_id: UUID):
    if agent_id not in agents_storage:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent = agents_storage[agent_id]
    
    current_state_dict = None
    if agent._context.current_state:
        current_state_dict = agent._context.current_state.model_dump()
    
    return AgentStateResponse(
        agent_id=agent.id,
        task=agent.task,
        state=agent.state.value,
        searches_used=agent._context.searches_used,
        clarifications_used=agent._context.clarifications_used,
        sources_count=len(agent._context.sources),
        current_state=current_state_dict
    )


@app.get("/agents", response_model=AgentListResponse)
async def get_agents_list():
    agents_list = [
        AgentListItem(
            agent_id=agent.id,
            task=agent.task,
            state=agent.state.value
        )
        for agent in agents_storage.values()
    ]
    
    return AgentListResponse(
        agents=agents_list,
        total=len(agents_list)
    )


def extract_task_from_messages(messages):
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    
    raise ValueError("User message not found in messages")


@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    if not request.stream:
        raise HTTPException(
            status_code=400, 
            detail="Only streaming responses are supported. Set 'stream=true'"
        )
    
    try:
        task = extract_task_from_messages(request.messages)
        agent = SGRResearchAgent(task=task)
        
        agents_storage[agent.id] = agent
        logger.info(f"Agent {agent.id} created and stored for task: {task[:100]}...")
        
        _ = asyncio.create_task(agent.execute())
        return StreamingResponse(
            agent.streaming_generator.stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Agent-ID": str(agent.id),  # Возвращаем ID агента в заголовке
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error completion: {e}")
        raise HTTPException(status_code=500, detail="str(e)")
