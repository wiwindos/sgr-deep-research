# 🧠 SGR Deep Research - Schema-Guided Reasoning System

https://github.com/user-attachments/assets/a5e34116-7853-43c2-ba93-2db811b8584a

Automated research system using Schema-Guided Reasoning (SGR). Two versions available: classic and enhanced streaming.

## 📁 Project Structure

```
sgr-deep-research/
├── sgr-classic/          # 🔍 Classic SGR version
│   ├── sgr-deep-research.py
│   ├── scraping.py
│   ├── config.yaml
│   ├── requirements.txt
│   └── README.md
│
├── sgr-streaming/        # 🚀 Enhanced streaming version
│   ├── sgr_streaming.py
│   ├── enhanced_streaming.py
│   ├── sgr_visualizer.py
│   ├── sgr_step_tracker.py
│   ├── demo_enhanced_streaming.py
│   ├── compact_streaming_example.py
│   ├── scraping.py
│   ├── config.yaml
│   ├── requirements.txt
│   └── README.md
│
└── reports/              # 📊 Generated reports
```

## 🚀 Quick Start

### Classic Version (Simple and stable)
```bash
cd sgr-classic
python sgr-deep-research.py
```

### Streaming Version (Modern with animations)
```bash
cd sgr-streaming
python sgr_streaming.py
```

## 🔍 Version Comparison

| Feature | SGR Classic | SGR Streaming |
|---------|-------------|---------------|
| **Interface** | Simple text | Interactive with animations |
| **JSON Parsing** | Static | Real-time streaming |
| **Visualization** | Basic | Schema trees + metrics |
| **Metrics** | Simple | Detailed + performance |
| **SGR Steps** | Text log | Visual pipeline |
| **Animations** | None | Spinners, progress bars |
| **Stability** | ✅ High | ✅ Stable |
| **Simplicity** | ✅ Maximum | Medium |
| **Functionality** | Basic | ✅ Extended |

## 🎯 Version Selection Guide

### Choose **SGR Classic** if:
- 🔧 Need simple and stable system
- 💻 Limited terminal resources
- 📝 Focus on results, not process
- 🚀 Quick deployment

### Choose **SGR Streaming** if:
- 🎨 Process visualization is important
- 📊 Need detailed metrics
- 🔍 Want to see real-time JSON parsing
- 🎬 Prefer modern interfaces

## ⚙️ General Setup

1. **Create config.yaml from example:**
```bash
cp config.yaml.example config.yaml
```

2. **Configure API keys:**
```yaml
openai:
  api_key: "your-openai-api-key"
  
tavily:
  api_key: "your-tavily-api-key"
```

3. **Install dependencies:**
```bash
# For classic version
cd sgr-classic && pip install -r requirements.txt

# For streaming version  
cd sgr-streaming && pip install -r requirements.txt
```

## 🎬 Demo (Streaming)

```bash
cd sgr-streaming

# Full feature demonstration
python demo_enhanced_streaming.py

# Compact streaming example
python compact_streaming_example.py
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

## 🔧 Configuration

### Main parameters:
```yaml
openai:
  model: "gpt-4o-mini"     # Model for reasoning
  max_tokens: 8000         # Maximum tokens
  temperature: 0.4         # Creativity (0-1)

execution:
  max_steps: 6            # Maximum SGR steps
  reports_dir: "reports"  # Reports directory

search:
  max_results: 10         # Search results count

scraping:
  enabled: false         # Web scraping
  max_pages: 5          # Maximum pages
```

## 📝 Reports

All reports are saved to `reports/` directory in format:
```
YYYYMMDD_HHMMSS_Task_Name.md
```

Reports contain:
- 📋 Executive summary
- 🔍 Technical analysis with citations
- 📊 Key findings  
- 📎 Sources list

## 🐛 Fixed Issues (Streaming)

✅ **Large gaps after streaming** - compact panels  
✅ **Planning step duplication** - proper tracking  
✅ **Clarification questions not displayed** - special handling  
✅ **Schema overlapping Completed block** - proper spacing  

## 🤝 Usage

Both versions are fully compatible and use the same configuration format. You can switch between them based on your needs.

---

🧠 **Choose the right SGR version for your research tasks!**
