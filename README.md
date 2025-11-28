<div align="center">

# 🌿 Treehopper Core

### The Agent Builder & Orchestration Automation Framework

<img src="treehopper/static/th_logo.png" alt="Treehopper Logo" width="180">

**Create, chain, and orchestrate autonomous agents — locally, on edge devices, or in distributed fleets.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-✔-green)](https://fastapi.tiangolo.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Memory-orange)](https://www.trychroma.com/)
[![LLM Providers](https://img.shields.io/badge/LLM%20Providers-OpenAI%20%7C%20Gemini%20%7C%20Perplexity-purple)](#)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen)](#)

</div>

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> What Is Treehopper?

**Treehopper** is a local-first, agent-centric, fully open-source automation framework for building intelligent workflows — from edge AI agents to orchestrated micro-services and distributed chains.

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Why This Project Matters

AI automation is rapidly becoming the backbone of modern software — yet the tooling around it remains fragmented, heavyweight, and increasingly centralized. Existing orchestrators either force developers into closed ecosystems, or bury simple ideas under layers of infrastructure complexity. Treehopper takes a different path. It brings AI orchestration back to where it belongs: *close to the developer*.

It brings together:

- ✔ Agent micro-apps
- ✔ Chain orchestration
- ✔ Multi-provider LLM calls
- ✔ Semantic memory
- ✔ Parallel execution
- ✔ Cancellation
- ✔ Edge-friendly deployment
- ✔ Portable FastAPI runtimes

### <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Core Principles

| | |
|---|---|
| 🟦 **Lightweight** | Run on laptops, VMs, Raspberry Pis, or edge nodes — no GPUs required |
| 🟩 **Modular** | Every agent and chain becomes its own FastAPI micro-service |
| 🟧 **Developer-first** | Build and debug everything via CLI with predictable logs, pids, URLs, and registries |
| 🟥 **Deterministic** | Repeatable runs, structured history, and precise observability |
| 🟪 **Cloud-optional** | You own the compute. You choose the LLM provider. No lock-in |

> **Treehopper is a statement:**
> AI automation should be open, simple, transparent, and fully in the developer's control.

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Why Treehopper?

| Feature | Description |
|---------|-------------|
| 🌱 **Local-first agent execution** | No cloud round-trips. No latency. No dependencies |
| 🔌 **Micro-app architecture** | Each agent becomes a standalone FastAPI micro-service with its own port |
| 🔄 **Chains = portable workflows** | Define multi-step flows with predictable inputs & outputs |
| 🧠 **Built-in memory** | Long-term semantic memory (ChromaDB) or ephemeral testing memory |
| ⚡ **Multi-LLM support** | Switch between OpenAI, Gemini, Perplexity, or local models seamlessly |
| 🧵 **Full orchestration core** | Parallel chains, throttling, cancellation, logging, history, safe cleanup |
| 🧩 **Edge deployment** | Package agents/chains to run on compute-limited devices |
| 🛠 **CLI for everything** | Build, lint, run, stop, inspect, clean, orchestrate |

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Quickstart

```bash
git clone <repo_url>
cd treehopper-core
pip install -r requirements.txt

# Start main server
treehopper run
```

**Open Swagger UI:**
[http://localhost:1567/docs](http://localhost:1567/docs)

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Project Structure

```
treehopper-core/
├── treehopper/
│   ├── agents/                    # Built-in agents
│   ├── utils/                     # Utilities & run registry
│   ├── treehopper.py              # Agent runtime, registry, chaining
│   ├── treehopper_llm.py          # Multi-provider LLM abstraction
│   ├── treehopper_cli.py          # Main CLI entrypoint
│   ├── agent_runtime_app.py       # Agent micro-app runtime
│   ├── chain_runtime_app.py       # Chain micro-app runtime (detached mode)
│   ├── treehopper_chains.py       # Chain controller + parallel + cancellation
│   ├── treehopper_parallel.py     # Parallel execution engine
│   ├── treehopper_cancellation.py # Cancellation API (Phase 3.3)
│   └── treehopper_cleaner.py      # Clean-up utility
├── examples/                      # Agent & chain usage
├── static/                        # Branding & assets
└── dashboard/                     # Optional UI
```

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Agent Development

### Create a new agent

```bash
treehopper init weather
```

This generates:

```
weather/
├── handler.py   # Your business logic
└── schema.py    # Request/response models
```

### Implement agent

```python
# handler.py
from treehopper.treehopper import agent

@agent("greet", method="GET", goal="Greet the user")
async def greet(name: str = "Nitin"):
    return {"message": f"Hello, {name}!"}
```

Agent becomes available at:

```
GET /api/v1/agents/greet?name=Nitin
```

### Deploy to main server

```bash
treehopper build weather
treehopper run
```

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Chaining Agents

```http
POST /api/v1/dev/chain
{
  "chain": [
    { "path": "/api/v1/agents/greet", "params": { "name": "Nitin" } },
    { "path": "/api/v1/agents/llm_compare", "params": { "prompt": "Write a haiku about agents" } }
  ]
}
```

Treehopper executes each step sequentially, passing outputs downstream.

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Multi-provider LLM Support

```python
await call_llm("What is edge AI?", provider="openai")
await call_llm("Explain solar energy", provider="gemini")
await call_llm("Compare wind vs hydro", provider="perplexity")
```

**Supported providers:**

- OpenAI (GPT-4o, GPT-4o-mini)
- Google Gemini Pro
- Perplexity (Mistral models)
- Local mock provider (for testing)

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Chain Runtime (Detached Mode)

Detached mode launches a full FastAPI runtime per chain, ideal for:

- ✔ Cancellation
- ✔ Long-running workflows
- ✔ Persistent runtimes
- ✔ Parallel orchestrators
- ✔ Offline edge execution

### Run chain in detached mode

```bash
treehopper chain run my_chain --detached
```

Starts:

```
http://localhost:<auto_port>/api/v1/<chain>/run
```

### Run detached in background

```bash
treehopper chain run my_chain --detached --bg
```

### Stop it

```bash
treehopper chain stop my_chain
```

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Parallel Execution (Phase 3.2)

Run a chain N times in parallel:

```bash
treehopper chain run my_chain --parallel 20 --concurrency 5
```

**Key points:**

- Parallelization occurs across chains, not inside a chain
- Throttle with `--concurrency` to avoid provider rate limits
- Each parallel run has its own run_id, history, results

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Cancellation (Phase 3.3)

Treehopper supports cooperative async cancellation, similar to Temporal/Celery but at the agent-chain-runtime level.

> **Note:** Cancellation works ONLY in detached mode, because only detached mode provides true async task lifecycles.

### 🟩 When Cancellation Works

| Scenario | Supported | Reason |
|----------|-----------|--------|
| `chain run --detached` | ✅ YES | Async micro-app maintains cancellable tasks |
| `chain run --detached --bg` | ✅ YES | Same as above |
| Cancelling by run_id | ✅ YES | Tracked in ACTIVE_TASKS |
| Cancelling all runs (`--all`) | ✅ YES | Cancels all active tasks for chain |
| Cancelling mid-agent (sleep, network calls, LLM waits) | ✅ YES | Cooperative awaits allow interruption |

### 🟥 When Cancellation Won't Work

| Scenario | Supported? | Why |
|----------|------------|-----|
| Normal chain run (non-detached) | ❌ NO | Blocking HTTP call; no async context |
| `--parallel` without detached | ❌ NO | Each run is a synchronous client request |
| `--parallel --detached` | ❌ NO | All parallel calls target one blocking endpoint |
| CPU-bound agents | ❌ NO | Cannot be cancelled without async yield |

### 🟦 Cancel Commands

**Cancel by run_id:**

```bash
treehopper chain cancel --run <run_id>
```

**Cancel all active runs of a chain:**

```bash
treehopper chain cancel --all <chain>
```

**Cancel an entire batch:**

```bash
treehopper chain cancel-batch <batch_id>
```

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Cleaning Up

```bash
treehopper clean
```

This command:

- Kills stuck uvicorn processes
- Removes pids/logs
- Resets registry (keeps subscription id)

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Full CLI Reference

### Main Server

| Command | Description |
|---------|-------------|
| `treehopper run` | Start main server |
| `treehopper run --bg` | Start in background |
| `treehopper stop` | Stop main server |
| `treehopper restart` | Restart |
| `treehopper status` | Check health |

### Agents

| Command | Description |
|---------|-------------|
| `treehopper init <agent>` | Scaffold new agent |
| `treehopper lint <agent>` | Validate |
| `treehopper build <agent>` | Install into registry |
| `treehopper agent run <agent> --detached` | Start as micro-app |

### Chains

| Command | Description |
|---------|-------------|
| `treehopper chain build` | Create chain |
| `treehopper chain run` | Run chain |
| `treehopper chain stop` | Stop chain runtime |
| `treehopper chain logs` | Show last run |
| `treehopper chain cancel` | Cancel run(s) |
| `treehopper chain cancel-batch` | Cancel batch |

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> License

**MIT License**

Treehopper is free for personal, commercial, edge, and enterprise usage.

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> Contributing

Pull requests, bug fixes, feature proposals, agent contributions, and ecosystem tools are welcome.

If you're building:

- An agent marketplace
- Edge AI system
- AI workflow automation SaaS
- Or a new orchestration platform

**We'd love to collaborate.**

---

## <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> The Vision

Treehopper is built on the belief that AI automation should be **democratized**.

- Not controlled by large platforms
- Not hidden behind proprietary runtimes
- Not tied to a single cloud provider

**Local-first. Open. Portable. Modular. Hackable. Developer-owned.**

If you believe in that future — **welcome to Treehopper.**

---

<div align="center">

Made with lot of hardwork <img src="treehopper/static/treehopper_favicon.png" alt="Treehopper Logo" width="20"> by me

</div>
