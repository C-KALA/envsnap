# envsnap

> Git for your dev environment. Capture, version, and replay your entire development environment as a JSON snapshot.

## The Problem

You finish a project. Move it to another machine. It breaks.

Your `.env` file stores secrets — but not Python versions, Docker versions, service startup order, or port assignments. That information lives silently in your OS. When you migrate, it disappears.

**envsnap fixes that.**

## How It Works

envsnap captures your entire dev environment as a versioned JSON snapshot — everything an AI or another developer needs to recreate it exactly.

## Installation

```bash
pip install envsnap
```

## Commands

| Command | What it does |
|---|---|
| `envsnap init` | Initialize envsnap in your project |
| `envsnap capture` | Take a snapshot of current environment |
| `envsnap log` | View snapshot history |
| `envsnap diff` | See what changed between snapshots |
| `envsnap replay` | Recreate environment from a snapshot |

## What Gets Captured

- Python version
- Pip version  
- Docker + Docker Compose versions
- All installed packages with exact versions
- Docker services, ports, dependencies, images
- Environment variable keys (never values)
- Active listening ports

## Quick Start

```bash
cd your-project
envsnap init
envsnap capture

# Move to new machine, clone your repo, then:
envsnap replay
```

## Real World Example

Built and tested on Omnium — a 9-service microservices project with Redis, PocketBase, FastAPI, and Telegram integration. envsnap captured all 9 services, 10 env keys, and exact versions in one command.

## Philosophy

- `.env` stores secrets. `project.snapshot` stores environment truth.
- Snapshots are JSON — readable by humans and AI agents.
- Works like Git — versioned, diffable, committable.
- Observation over declaration — captures what actually runs, not what you think runs.

## Requirements

- Python 3.10+
- Linux (Debian/Ubuntu recommended)
- Docker (optional)

## License

MIT — Chetan Kala (github.com/C-KALA)
