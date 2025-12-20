# Contributing to TreehopperAI

First of all — thank you for considering contributing to **TreehopperAI** 🌱
This project is built to empower developers to create, orchestrate, and run AI agents locally and at scale.

We welcome contributions of all kinds:
- Bug fixes
- New agents
- New chains
- Performance improvements
- Documentation
- Examples and demos
- Tooling around Treehopper

---

## 🧭 Project Philosophy

TreehopperAI follows a few core principles:

- **Local-first** — everything should run local first with optional cloud/llm dependency
- **CLI-first** — predictable behavior via terminal, logs, and files
- **Agents & chains are services** — every unit must be runnable independently
- **Detached runtimes are sacred** — cancellation, replay, and observability matter
- **No magic** — explicit state, explicit logs, explicit lifecycle

Please keep these in mind when contributing.

---

## 🛠 Development Setup

```bash
git clone https://github.com/nitin-karma/treehopper-core.git
cd treehopper-core
pip install -e .
Run the main server:

th start --bg
```

## Swagger UI:
```
http://localhost:1567/docs

```
## 🧪 Testing Strategy

### Treehopper uses layered testing:

- Unit tests (fast, isolated)
pytest tests/unit

- Integration tests (registry + runtime)
pytest tests/integration

- Real E2E tests (CLI-based, user-facing)
scripts/e2e_smoke_treehopper_full.sh

- ⚠️ E2E tests are NOT written in pytest by design
They must run exactly how users run Treehopper.

### 🧩 Contributing Agents
```
Agents live under:

examples/<agent_name>/
├── handler.py
├── schema.py
└── agent.yaml
```

### Requirements:
- Clear input/output schema
- Deterministic behavior in mock mode
- Must be built and run via:

```
th build <agent_name>
th lint <agent_name>
th call <agent_name> '{}'

```
### To create a separate runtime for the same agent
```
th agent start <agent_name> --detached

```
### 🔗 Contributing Chains
Chains must:
- Be reproducible
- Use existing agents
- Support detached mode
- Emit meaningful step events

```
Use:

th chain build <chain_name> <agent_name> <agent_name>
th chain start <chain_name> --detached --port <port>
th chain run <chain_name> --payload '{}' --detached

```
### 📐 Code Style & Logging

- Python 3.10+
- Prefer explicit functions over magic
- Use logging.getLogger(__name__)
- Avoid global side effects
- Never break CLI contracts

## 📦 Dependency Rules

- Avoid heavy dependencies unless necessary
- Any new dependency must be justified
- No vendor API calls in tests

## 📄 Licensing
```
By contributing, you agree that your contributions will be licensed under the MIT License.

```

## 🤝 Need Help?

- Open a GitHub Issue
- Start a Discussion
- Or tag maintainers in PRs

### We’re building something meaningful — together.
### 🚀 Welcome to TreehopperAI.
