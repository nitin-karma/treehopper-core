<p>
  <img src="treehopper/logo/th_logo.PNG" alt="Treehopper Logo" width="200" style="vertical-align: middle; margin-right: 8px;">
</p>



Treehopper is a modular agentic automation framework built with FastAPI. It enables developers to create, chain, and deploy autonomous agents with ease.

## 🚀 Features

- Modular agent discovery via decorators
- Chaining and orchestration via `/chain`
- Multi-provider LLM support (OpenAI, Perplexity, Gemini)
- Semantic memory with ChromaDB
- CLI tooling and test suite
- Slack, GitHub, PDF, and math agents included

## 🧪 Quickstart

```bash
pip install -r requirements.txt
treehopper run


🧠 Create an Agent

@agent("/greet", method="GET", goal="Greet the user")
async def greet(name: str = "Nitin"):
    return {"message": f"Hello, {name}!"}


🔗 Chain Agents

{
  "chain": [
    { "path": "/greet", "params": { "name": "Nitin" } },
    { "path": "/prompt", "params": { "prompt": "Write a haiku about agents" } }
  ]
}


🧠 LLM Providers

• OpenAI (GPT-4)
• Perplexity (Mistral)
• Gemini (Pro)


📁 Folder Structure

treehopper/
├── agents/                    # Modular agent definitions (auto-discovered)
│   ├── greet.py
│   ├── prompt_agent.py
│   ├── llm_providers.py
│   ├── llm_test.py
│   ├── llm_compare.py
│   └── ... (more agents)
│
├── dashboard/                 # Optional: React-based UI for chaining and testing
│   ├── public/
│   └── src/
│       ├── components/
│       ├── pages/
│       └── App.jsx
│
├── logo/                      # Branding assets
│   ├── treehopper_logo.png
│   ├── treehopper_app_icon.png
│   └── treehopper_favicon.png
│
├── tests/                     # Pytest test suite
│   └── test_treehopper.py
│
├── treehopper/                # Core framework package
│   ├── __init__.py
│   ├── treehopper.py          # Core app, agent decorator, chaining, memory
│   ├── treehopper_llm.py      # Multi-provider LLM support
│   └── treehopper_cli.py      # CLI tool
│
├── .env.example               # Sample API key config
├── .gitignore
├── LICENSE
├── README.md                  # Full usage guide, examples, architecture
├── requirements.txt
├── setup.py                   # For pip installability
└── pyproject.toml             # Optional: for modern packaging
