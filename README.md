<p align="left">
  <img src="treehopper/static/th_logo.png" alt="Treehopper Logo" width="180">
</p>

<h2 align="left">The Agent Builder and Orchestration Automation Framework</h2>

<p align="left">
  <strong>Create, chain, and deploy autonomous agents — locally or on the edge.</strong>
</p>
<br/>

<p align="left">
  <img src="https://img.shields.io/badge/python-3.9+-blue" />
  <img src="https://img.shields.io/badge/FastAPI-✔-green" />
  <img src="https://img.shields.io/badge/ChromaDB-Memory-orange" />
  <img src="https://img.shields.io/badge/LLM%20Providers-OpenAI%20%7C%20Gemini%20%7C%20Perplexity-purple" />
  <img src="https://img.shields.io/badge/Status-Active-brightgreen" />
</p>

---

### <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> What is Treehopper?

Treehopper is a **modular agentic framework** built on FastAPI that allows developers to:

- Define **agents** using a lightweight decorator
- **Chain multiple agents** into workflows using a single POST endpoint
- Use **semantic memory** backed by ChromaDB
- Call **multiple LLM providers** interchangeably
- Deploy agents locally, on edge devices, or in the cloud

Treehopper is built for **AI automation, RPA, decision systems, IoT edge coordination, and agent marketplaces.**

---

###  <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Key Features

| Capability | Status |
|----------|--------|
| Auto-discovered agent modules | ✔ |
| GET / POST agent execution | ✔ |
| Runtime chaining with `/api/v1/dev/chain` | ✔ |
| ChromaDB semantic memory | ✔ |
| Ephemeral in-memory memory for pytest | ✔ |
| Multi-provider LLM support | ✔ |
| CLI support (`treehopper run / call / build`) | ✔ |
| Full test suite | ✔ |

---

###  <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Quickstart

```bash
git clone <repo_url>
cd treehopper-core
pip install -r requirements.txt
treehopper run
Then open -> http://localhost:1560/docs   → Swagger UI
```

###  🔧 Treehopper CLI Commands
```
Treehopper includes a built-in CLI for running, testing, and invoking agents directly from the terminal.
```

| Command | Description |
| :--- | :--- |
| `treehopper run` | Start the FastAPI server (auto-discovers agents) |
| `treehopper call <path> <json_params>` | Invoke an agent directly from CLI without starting server |
| `treehopper build` | Package a folder-based agent into a distributable bundle |
| `treehopper lint` | Validate agent schema/handler format |
| `treehopper init <name>` | Scaffold a new folder-based agent |
| `treehopper version` | Show current installed framework version |
| `treehopper help` | Display command reference |
```
Example Usage:
 - Scaffolding a New Agent
  treehopper init weather
          ->  creates
                -> ~/.treehopper/registry/agents/weather/
                    ├── schema.py ->> add your pydantic models
                    └── handler.py ->> write your helper python functions to run agent

- To deploy the agent to main server
  treehopper build weather
          ->  Push the agent to default main server

 - Auto-discovered on next
  treehopper run
          -> updates the main server to have new agent running

- Chain the agent
  treehopper call /api/v1/dev/chain \
      '{
          "chain": [
              {"path": "/api/v1/agents/greet", "params": {"name": "Alpha"}},
              {"path": "/api/v1/agents/math", "params": {"a": 2, "b": 3}}
          ]
    }'

```
### <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Creating an Treehopper Agent using Python code
```
from treehopper.treehopper import agent

@agent("/greet", method="GET", goal="Greet the user")
async def greet(name: str = "Nitin"):
    return {"message": f"Hello, {name}!"}

The agent automatically becomes available at:
GET /api/v1/agents/greet?name=Nitin

```

### <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Chaining Agents
```
POST /api/v1/dev/chain
{
  "chain": [
    { "path": "/api/v1/agents/greet", "params": { "name": "Nitin" } },
    { "path": "/api/v1/agents/llm_compare", "params": { "prompt": "Write a haiku about agents" } }
  ]
}

Treehopper executes workflows sequentially, passing results back to the caller.
```

### <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Multi-Provider LLM Support
```
await call_llm("Explain quantum computing", provider="openai")
await call_llm("Explain recycling benefits", provider="gemini")
await call_llm("Solar vs Wind comparison", provider="perplexity")

Providers supported:
 - OpenAI (GPT-4o / GPT-4o-mini)
 - Gemini (Pro)
 - Perplexity (Mistral-7B)
```

### <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Project Structure
```
treehopper/
├── treehopper/                # Core framework
│   ├── treehopper.py          # Runtime, registry, chaining, memory
│   ├── treehopper_llm.py      # Multi-LLM abstraction
│   └── treehopper_cli.py      # CLI
├── agents/                    # Auto-discovered built-in agents
├── static/                    # Branding assets
├── tests/                     # Pytest suite
└── dashboard/                 # Optional React developer UI
```

### <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> ./clean.sh Shell Script
```
To Cleanup -
- Cleaning treehopper memory
- Python caches
- Kill running uvicorn server
- Remove installed agents (keep subscription id)

```

### <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> License
```
Treehopper is available under the MIT License.
```

### <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Contributing
```
Pull requests and community-built agents are welcome!
If you're building an agent marketplace or startup around Treehopper — we’d love to collaborate.
```
