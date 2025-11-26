<p align="left">
  <img src="treehopper/static/th_logo.png" alt="Treehopper Logo" width="180">
</p>

<h2 align="left">The Agent Builder and Orchestration Automation Framework</h2>

<p align="left">
  <strong>Create, chain, and deploy autonomous agents — locally or on the edge.</strong>
</p>
<br/>

<p align="left">
  <img src="https://img.shields.io/badge/python-3.10+-blue" />
  <img src="https://img.shields.io/badge/FastAPI-✔-green" />
  <img src="https://img.shields.io/badge/ChromaDB-Memory-orange" />
  <img src="https://img.shields.io/badge/LLM%20Providers-OpenAI%20%7C%20Gemini%20%7C%20Perplexity-purple" />
  <img src="https://img.shields.io/badge/Status-Active-brightgreen" />
</p>

---

### <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> What is Treehopper? - Motivation

Treehopper is built on a simple but powerful belief — that AI workflows shouldn’t be locked behind massive cloud platforms, vendor lock-in, or enterprise-grade complexity. Developers deserve tools that are fast, local-first, hackable, and fully in their control. Treehopper re-imagines how agents, chains, and intelligent micro-services should run: lightweight, modular, portable, and fun to build with. This project is not just open-source code — it’s a mission to empower every developer to orchestrate AI on their own terms, from a single laptop to a global fleet. If that excites you, you’re in the right place. Welcome to Treehopper. 🌿


### <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Why This Project Matters

AI automation is rapidly becoming the backbone of modern software — yet the tooling around it remains fragmented, heavyweight, and increasingly centralized. Existing orchestrators either force developers into closed ecosystems, or bury simple ideas under layers of infrastructure complexity. Treehopper takes a different path. It brings AI orchestration back to where it belongs: *close to the developer*.

Treehopper matters because it enables:

### • **Local-first agent execution**
Run AI workflows without GPUs, cloud dependencies, or latency-sensitive round-trips — ideal for privacy-critical, cost-sensitive, or offline-first applications.

### • **Modular micro-app architecture**
Every agent and chain runs as an independent FastAPI micro-service, with predictable ports, isolated runtimes, and complete transparency.

### • **A CLI designed for builders**
No dashboards required. Spin up agents, run chains, inspect logs, manage history, and orchestrate complex flows — all from your terminal.

### • **Deterministic & repeatable workflows**
Treehopper gives developers the reliability and observability of enterprise orchestrators, but with zero vendor lock-in.

### • **A real alternative to centralized AI platforms**
As AI ecosystems become more closed, Treehopper stands for autonomy. You own your workflows, your data, your compute, and your future.

Treehopper is more than a framework — it’s a statement about how AI tooling should evolve: open, accessible, transparent, and developer-first. If you believe in that vision, join us and help shape the next generation of AI infrastructure.


### • Treehopper in a core its a **modular agentic framework** built on FastAPI that allows developers to:

- Define **agents** using a lightweight decorator
- **Chain multiple agents** into workflows using a single POST endpoint
- Use **semantic memory** backed by ChromaDB
- Call **multiple LLM providers** interchangeably
- Deploy agents locally, on edge devices, or in the cloud
- Stabilize the agent and chain execution and making it observable.

Treehopper is **clean, repeatable, scalable agent server** built for **AI automation, RPA, decision systems, IoT edge coordination, and agent marketplaces.**

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

# Treehopper CLI Commands

### Main Server/Process Commands

| Command                     | Description                                                                 |
|-----------------------------|-----------------------------------------------------------------------------|
| `treehopper status`         | Show if the main server is running                                          |
| `treehopper run`            | Start the main server                                                       |
| `treehopper run --bg`       | Start the main server in background                                         |
| `treehopper stop`           | Stop the main server                                                        |
| `treehopper restart`        | Restart main server                                                         |
| `treehopper list`           | List installed agents                                                       |
| `treehopper clean`          | **Be Careful** - Cleanup servers, pids, agents, chain                       |

### Agent Related CLI Commands

| Command                                         | Description                                                                 |
|-------------------------------------------------|-----------------------------------------------------------------------------|
| `treehopper push-file <agent-name> <file_path>` | Push input file to agent for file operations                                |
| `treehopper call <path> '<json>'`               | Call an agent                                                               |
| `treehopper init <agent_name>`                  | Create agent scaffold template                                              |
| `treehopper lint <agent_folder>`                | Validate `handler.py` + YAML                                                |
| `treehopper build <agent_folder>`               | Install agent to registry and make it available with main server            |
| `treehopper agent info <ref>`                   | Show metadata                                                               |
| `treehopper agent run <name> --detached [--bg]` | Start dedicated agent runtime (optionally in background)                    |
| `treehopper agent delete <ref>`                 | Delete installed agent safely                                               |

### Chain Related CLI Commands

| Command               | Description                                                                 |
|-----------------------|-----------------------------------------------------------------------------|
| `treehopper chain`    | View all Chain related commands                                             |

### Treehopper Chain Commands

| Command                                                                 | Description                                                                 |
|-------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `treehopper chain build <name> <agent1> <agent2> ...`                   | Register a named chain using registered agents. Creates chain YAML + POST endpoint `/api/v1/chains/<name>` |
| `treehopper chain run <name or id> [--payload '{...}'] [--payload-file path] [--detached] [--bg]` | Execute a named chain via `/api/v1/chains/{name}`. Payload passed only to first agent. Options: `--detached` (dedicated micro-app), `--bg` (background logs). |
| `treehopper chain stop <name or id>`                                       | Stop a dedicated chain runtime if running                                   |
| `treehopper chain delete <name or id>`                                     | Delete chain metadata and last run logs                                     |
| `treehopper chain logs <name or id>`                                       | Show last execution summary + JSON                                          |
| `treehopper chain <agent_path1> <agent_path2> ...` (Legacy)             | Direct call to `/api/v1/dev/chain` with static agent paths                  |

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
treehopper-core/
├── treehopper/                # Core framework
|   ├── agents                 # built in agent ednpoints
|   ├── utils                  # utility module
│   ├── treehopper.py          # Runtime, registry, chaining, memory
│   ├── treehopper_llm.py      # Multi-LLM abstraction
│   └── treehopper_cli.py      # CLI
|   └── agent_runtime_app.py   # To launch an agent as micro-app
|   └── chain_runtime_app.py   # To launch an agent connected chain as micro-app
|   └── treehopper_chains.py   # Chains controller
|   └── treehopper_cleaner.py  # To clean the runtimes / logs / pids
├── examples/                  # built-in as examples
├── static/                    # Branding assets
└── dashboard/                 # Optional UI
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
