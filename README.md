# 🧠 SGR Deep Research - Schema-Guided Reasoning API

https://github.com/user-attachments/assets/a5e34116-7853-43c2-ba93-2db811b8584a

Production-ready FastAPI service for automated research using Schema-Guided Reasoning (SGR). Features real-time streaming responses and comprehensive research capabilities.

## 📁 Project Structure

```
sgr-deep-research/
├── src/                     # 🎯 Main application source
│   ├── api/                 # 🌐 FastAPI endpoints and models
│   │   ├── endpoints.py     # API routes and handlers
│   │   └── models.py        # Pydantic models for API
│   ├── core/                # 🧠 Core SGR logic
│   │   ├── agent.py         # Main research agent
│   │   ├── models.py        # Data models
│   │   ├── reasoning_schemas.py  # SGR reasoning schemas
│   │   ├── stream.py        # Streaming infrastructure
│   │   └── tools.py         # Research tools
│   ├── services/            # 🔧 External integrations
│   │   └── tavily_search.py # Search service
│   ├── main.py              # 🚀 Application entry point
│   └── settings.py          # ⚙️ Configuration management
├── reports/                 # 📊 Generated research reports
├── config.yaml.example     # 📝 Configuration template
├── docker-compose.yml      # 🐳 Docker deployment
└── requirements.txt        # 📦 Dependencies
```

## 🚀 Quick Start

### Local Development
```bash
# 1. Setup configuration
cp config.yaml.example config.yaml
# Edit config.yaml with your API keys

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
cd src && python main.py
```

### Docker Deployment
```bash
# 1. Setup configuration
cp config.yaml.example src/config.yaml
# Edit src/config.yaml with your API keys

# 2. Deploy with Docker Compose
docker-compose up -d

# 3. Check health
curl http://localhost:8010/health
```

## 🌐 API Usage

### OpenAI-Compatible Chat Completions
```bash
curl -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Research BMW X6 2025 prices in Russia"}],
    "stream": true
  }'
```

### Agent Management
```bash
# Get all agents
curl http://localhost:8010/agents

# Get specific agent state
curl http://localhost:8010/agents/{agent_id}/state

# Provide clarification to waiting agent
curl -X POST "http://localhost:8010/agents/{agent_id}/provide_clarification" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Focus on luxury models only"}],
    "stream": true
  }'
```

## 📊 SGR Capabilities

### Schema-Guided Reasoning includes:
1. **🤔 Clarification** - clarifying questions when unclear
2. **📋 Plan Generation** - research plan creation  
3. **🔍 Web Search** - internet information search
4. **🔄 Plan Adaptation** - plan adaptation based on results
5. **📝 Report Creation** - detailed report creation
6. **✅ Completion** - task completion

### Example tasks:
- "Find information about BMW X6 2025 prices in Russia"
- "Research current AI trends"
- "Analyze cryptocurrency market in 2024"

## 🧠 Why SGR + Structured Output?

### The Problem with Function Calling on Local Models
**Reality Check:** Function Calling works great on OpenAI/Anthropic (80+ BFCL scores) but fails on local models <32B parameters.

**Test Results:**
- `Qwen3-4B`: Only 2% accuracy in Agentic mode (BFCL benchmark)
- Local models know **HOW** to call tools, but not **WHEN** to call them
- Result: `{"tool_calls": null, "content": "Text instead of tool call"}`

### SGR Solution: Forced Reasoning → Deterministic Execution

```python
# Phase 1: Structured Output reasoning (100% reliable)
reasoning = model.generate(format="json_schema")

# Phase 2: Deterministic execution (no model uncertainty)  
result = execute_plan(reasoning.actions)
```

### Architecture by Model Size

| Model Size | Recommended Approach | Why |
|------------|---------------------|-----|
| **<14B** | Pure SGR + Structured Output | FC accuracy too low, SO forces reasoning |
| **14-32B** | SGR as tool + FC hybrid | Best of both worlds |
| **32B+** | Native FC + SGR fallback | FC works reliably |

### SGR vs Function Calling

| Aspect | Traditional FC | SGR + Structured Output |
|--------|---------------|------------------------|
| **When to think** | Model decides ❌ | Always forced ✅ |
| **Reasoning quality** | Unpredictable ❌ | Structured & consistent ✅ |
| **Local model support** | <35% accuracy ❌ | 100% on simple tasks ✅ |
| **Deterministic** | No ❌ | Yes ✅ |

**Bottom Line:** Don't force <32B models to pretend they're GPT-4o. Let them think structurally through SGR, then execute deterministically.

## ⚙️ Configuration

### Setup Configuration File
1. **Create config.yaml from template:**
```bash
cp config.yaml.example config.yaml
```

2. **Configure API keys:**
```yaml
openai:
  api_key: "your-openai-api-key-here"
  model: "gpt-4o-mini"
  max_tokens: 8000
  temperature: 0.4

tavily:
  api_key: "your-tavily-api-key-here"

search:
  max_results: 10

scraping:
  enabled: false
  max_pages: 5
  content_limit: 1500

execution:
  max_steps: 6
  reports_dir: "reports"
```

### Environment Variables (Alternative)
```bash
export OPENAI_API_KEY="your-openai-key"
export TAVILY_API_KEY="your-tavily-key"
export HOST="0.0.0.0"
export PORT="8010"
```

### Server Configuration
```bash
# Custom host and port
python main.py --host 127.0.0.1 --port 8080

# Custom config file
python main.py --app_config /path/to/config.yaml
```

## 📝 Reports

Research reports are automatically saved to the `reports/` directory in Markdown format:
```
reports/YYYYMMDD_HHMMSS_Task_Name.md
```

### Report Structure
- 📋 **Executive Summary** - Key insights overview
- 🔍 **Technical Analysis** - Detailed findings with citations
- 📊 **Key Findings** - Main conclusions
- 📎 **Sources** - All reference links

### Example Report
See `example_report.md` for a complete sample of SGR research output.

## 🔗 Integration Examples

### Python Client
```python
import httpx

async def research_query(query: str):
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8010/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": query}],
                "stream": True
            }
        ) as response:
            async for chunk in response.aiter_text():
                print(chunk, end="")
```

### Curl with Streaming
```bash
curl -N -X POST "http://localhost:8010/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Research current AI trends"}],
    "stream": true
  }'
```

### Agent State Monitoring
```python
import httpx

async def monitor_agent(agent_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8010/agents/{agent_id}/state")
        state = response.json()
        
        print(f"Task: {state['task']}")
        print(f"State: {state['state']}")
        print(f"Searches used: {state['searches_used']}")
        print(f"Sources found: {state['sources_count']}")
```

## 🚦 Health Check & Monitoring

### Health Endpoint
```bash
curl http://localhost:8010/health
```



### Production Readiness
- ✅ **Structured logging** with proper log levels
- ✅ **Health checks** for container orchestration  
- ✅ **Graceful error handling** with HTTPException
- ✅ **Async/await** throughout for performance
- ✅ **Pydantic validation** for all inputs/outputs
- ✅ **Environment variable** support
- ✅ **Docker containerization** with multi-stage builds

## 🎯 Example Research Tasks

The SGR system excels at various research scenarios:

- **Market Research**: "Analyze BMW X6 2025 pricing across European markets"
- **Technology Trends**: "Research current developments in quantum computing"
- **Competitive Analysis**: "Compare features of top 5 CRM systems in 2024"
- **Industry Reports**: "Investigate renewable energy adoption in Germany"

## 🤝 Contributing

SGR Deep Research is designed as a production-ready service. The new architecture supports:

- **Extensible reasoning schemas** in `src/core/reasoning_schemas.py`
- **Pluggable search services** in `src/services/`
- **Clean API interfaces** with comprehensive models
- **Streaming responses** for real-time user experience

---

🧠 **Production-ready Schema-Guided Reasoning for automated research!**
