# 🔍 SGR Classic - Schema-Guided Reasoning

Classic version of Schema-Guided Reasoning system for automated research.

## 📁 Files

- **`sgr-deep-research.py`** - main classic SGR system file
- **`scraping.py`** - web scraping and content extraction utilities
- **`config.yaml`** - configuration file

## 🚀 Usage

```bash
# Navigate to directory
cd sgr-classic

# Run classic version
python sgr-deep-research.py
```

## ✨ Features

- ✅ Classic output interface
- ✅ Step-by-step SGR execution
- ✅ Basic performance metrics
- ✅ Standard JSON parsing
- ✅ Simple and stable

## 📋 Configuration

Copy `config.yaml.example` to `config.yaml` and configure:

```yaml
openai:
  api_key: "your-api-key"
  model: "gpt-4o-mini"
  
tavily:
  api_key: "your-tavily-key"
```

## 🔧 Requirements

```bash
pip install openai tavily-python pydantic rich
```