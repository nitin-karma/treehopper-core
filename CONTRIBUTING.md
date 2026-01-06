# Contributing to TreehopperAI 🌱

First of all — thank you for considering contributing to **TreehopperAI**.

TreehopperAI is a local-first agent orchestration runtime designed for clarity,
control, and real-world execution. Contributions of all kinds are welcome.

---

## 🧭 Project Philosophy

TreehopperAI follows a few non-negotiable principles:

- **Local-first** — everything runs locally by default
- **CLI-first** — predictable behavior via commands, logs, and files(70+ CLI cmds)
- **Agents & chains are services** — every unit must run independently
- **Detached runtimes matter** — cancellation, replay, observability are core
- **No magic** — explicit state, explicit lifecycle, explicit errors

#### Contributions are welcome:
- Bug fixes
- New agents
- New chains
- Performance improvements
- Documentation
- Examples and demos
- Tooling around Treehopper

Please keep these in mind when contributing.

---

## 🌿 Branching & Workflow

TreehopperAI uses a **PR-based workflow**.

### Branches

| Branch | Purpose |
|------|--------|
| `main` | Stable, production-ready releases |
| `develop` | Active development & integration |
| `feature/*` | New features |
| `fix/*` | Bug fixes |
| `docs/*` | Documentation changes |

### Workflow

```bash
# Always start from develop
git checkout develop
git pull origin develop

# Create a feature branch
git checkout -b feature/my-change

# Work & commit
git commit -m "feat: describe your change"

# Push and open PR → develop
git push origin feature/my-change

```

### 🚨 Direct pushes to main or develop are not allowed.
All changes must go through Pull Requests with CI passing.

### 🛠 Development Setup
```
git clone <repo_url>
cd treehopper-core
pip install -e .

# Setup the Workspace for development(do not create in same cloned directory)
cd ..
[treehopper / th] workspace create <n>

# Setup the execution root
[treehopper / th] setup

# View available commands
[treehopper / th] whatis
[treehopper / th] help
[treehopper / th] chain help

# Start main server
[treehopper / th] start --bg

```

### 🧪 Testing Strategy
```
Treehopper uses layered testing:

- Unit tests

pytest tests/unit


- Integration tests

pytest tests/integration


- E2E smoke tests (CLI-based)

scripts/e2e_smoke_treehopper_full.sh


- ⚠️ E2E tests intentionally run like real users and are not written in pytest.

```

### 🧩 Example Agents
Agents typically live under:
```
examples/<agent_name>/
├── handler.py
├── schema.py
└── agent.yaml

- Requirements
Clear input/output schema
Deterministic behavior in mock mode
Must pass:

th lint <agent>
th build <agent>
th call <agent> '{}'

```

### 🔗 Contributing Chains
#### Chains must:
- Be reproducible
- Use existing agents
- Support detached mode
- Emit meaningful step events

```
th chain build <chain_name> <agent1> <agent2>
th chain start <chain_name> --detached
th chain run <chain_name> --payload '{}' --detached

```

### 📐 Code Style & Rules
- Python 3.10+
- Explicit > implicit
- Prefer readability over cleverness
- Use structured logging
- Never break CLI contracts
- No hidden network calls in tests

### 📦 Dependencies
- Avoid heavy dependencies unless justified
- New dependencies must be explained in PR
- No vendor API calls in CI or tests

### 📄 License
By contributing, you agree that your work is licensed under the MIT License.

### 🤝 Need Help?
- Open a GitHub Issue
- Start a Discussion
- Comment on a PR

### 🚀 We’re building something real — welcome to TreehopperAI.
