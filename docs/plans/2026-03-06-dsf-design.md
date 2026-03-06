# Dark Software Factory (DSF) — Design Document

## Overview

DSF is an automated code generation pipeline that runs Claude Code inside an ephemeral systemd-nspawn container. Tasks are submitted via CLI, processed by a persistent worker daemon, and results are pushed to GitHub.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Host (Arch Linux)                              │
│                                                 │
│  ┌──────────┐   ┌───────────────────────────┐   │
│  │ dsf CLI   │──▶│  SQLite Task DB            │   │
│  └──────────┘   └───────────┬───────────────┘   │
│                              │                   │
│  ┌───────────────────────────▼───────────────┐   │
│  │  Worker Daemon (dsf worker)               │   │
│  │  - Polls DB for pending tasks             │   │
│  │  - Invokes machinectl shell → claude      │   │
│  │  - Captures output, updates status        │   │
│  │  - Pushes results to GitHub               │   │
│  └───────────────────────────┬───────────────┘   │
│                              │                   │
│  ┌───────────────────────────▼───────────────┐   │
│  │  systemd-nspawn container (dsf-factory)   │   │
│  │  - Arch minimal + base-devel + git + gh   │   │
│  │  - Claude Code (--dangerously-skip-perms) │   │
│  │  - Claude Max OAuth session (ro mount)    │   │
│  │  - /workspace bind-mount per task         │   │
│  └───────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

## Task Lifecycle

```
submitted → running → pushing → completed
                 ↘        ↘
                  failed    failed
```

### Data Model

```sql
CREATE TABLE tasks (
    id           INTEGER PRIMARY KEY,
    petname      TEXT UNIQUE NOT NULL,    -- human-readable ID (e.g. "swift-otter")
    name         TEXT NOT NULL,           -- short project name
    prompt       TEXT NOT NULL,           -- full prompt/spec for Claude
    github_repo  TEXT,                    -- target repo (e.g. "jeff/my-web-app")
    status       TEXT DEFAULT 'submitted', -- submitted|running|pushing|completed|failed
    error        TEXT,                    -- error message if failed
    created_at   TEXT DEFAULT (datetime('now')),
    started_at   TEXT,
    completed_at TEXT
);
```

### Worker Flow (per task)

1. Claim task (set status=running, started_at=now)
2. Create `/workspace/{task.name}` inside the container
3. `git init` + configure remote using `github_repo`
4. Run `claude --dangerously-skip-permissions -p "{task.prompt}"` inside container via `machinectl shell`
5. On success: commit all, push to GitHub, set status=completed
6. On failure: capture stderr, set status=failed with error

## Container Setup

### Bootstrap (`dsf init`)

- `pacstrap` an Arch rootfs into `/var/lib/machines/dsf-factory`
- Install: `base-devel git github-cli nodejs npm`
- Install Claude Code: `npm install -g @anthropic-ai/claude-code`
- Create non-root `worker` user

### Authentication

| Credential | Method |
|------------|--------|
| Claude Max | Bind-mount `~/.claude/` → `/home/worker/.claude/` (ro) |
| GitHub | Fine-grained PAT stored in `~/.dsf/config.toml`, injected as `GH_TOKEN` env var |

No host GitHub credentials are mounted. The user provides a dedicated, permission-scoped PAT during `dsf init`.

### Networking

Host networking (no `--network-veth`). Container needs internet for package installation, git, and GitHub API.

### Bind Mounts

| Host path | Container path | Mode |
|-----------|---------------|------|
| `~/.claude/` | `/home/worker/.claude/` | ro |
| `~/.dsf/workspaces/` | `/workspace/` | rw |

## CLI Interface

```bash
dsf init                                          # Bootstrap container + config
dsf submit --repo REPO "prompt"                   # Submit from string
dsf submit --repo REPO --file spec.md             # Submit from file
dsf status                                        # List all tasks
dsf status PETNAME                                # Detail for one task
dsf logs PETNAME                                  # Show Claude Code output
dsf worker                                        # Start worker daemon
dsf destroy                                       # Tear down container
```

All user-facing task references use petnames (e.g. `swift-otter`, `calm-badger`), generated via the `petname` package at submission time.

## Configuration

```toml
# ~/.dsf/config.toml
[github]
token = "github_pat_..."

[container]
name = "dsf-factory"
image_path = "/var/lib/machines/dsf-factory"

[worker]
poll_interval = 5  # seconds
```

## Logging

- Worker daemon: `~/.dsf/logs/worker.log` (structured, with rotation)
- Per-task output: `~/.dsf/logs/task-{petname}.log`
- `dsf logs PETNAME` tails the task log

## Project Structure

```
dsf/
├── pyproject.toml
├── src/
│   └── dsf/
│       ├── __init__.py
│       ├── cli.py          # click CLI
│       ├── db.py           # SQLite operations
│       ├── worker.py       # Worker daemon loop
│       ├── container.py    # nspawn/machinectl interactions
│       ├── config.py       # TOML config loading
│       └── init.py         # Container bootstrap logic
└── tests/
```

## Technology Choices

- **Python** with UV for package management
- **click** for CLI
- **SQLite** for task queue (simple, no external deps)
- **systemd-nspawn** / **machinectl** for container management
- **petname** for human-readable task IDs
- **ruff** for linting/formatting, **mypy** for type checking
