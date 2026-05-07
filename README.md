# NLM Bible Translation Platform

A desktop application for managing Bible translation projects in low-resource languages. Built with Electron, React, FastAPI, and MongoDB, with AI-assisted translation via local LLMs, OpenRouter, or Anthropic API 

Translators work through a three-resource model per language: **Bible texts** (verse-by-verse with human verification), **Dictionary** (building a lexicon as you translate), and **Memories** (grammar notes, language observations, correction history). An integrated chat interface connects to Claude or a local LLM for context-aware translation assistance with tool use.

## Architecture

```
+---------------------------------------------------+
|              Electron Desktop App                  |
|  +---------------------------------------------+  |
|  |           React Renderer (Vite)              |  |
|  |  Homepage > LanguageProject > Viewers        |  |
|  |  ChatDrawer (AI chat side panel)             |  |
|  +---------------------------------------------+  |
|  |           Main Process (Webpack)             |  |
|  |  mongod-manager | backend-manager | IPC      |  |
|  +---------------------------------------------+  |
+---------------------------------------------------+
         |                        |
         | MongoDB (port 27019)   | HTTP REST (port 8221)
         v                        v
+----------------+    +------------------------+
| ~/.nlm/bin/    |    | FastAPI Backend         |
| mongod         |    | 20 route modules       |
| ~/.nlm/db/     |    | MCP server (Claude)    |
+----------------+    | LLM tool loop (chat)   |
                      +------------------------+
                               |
                      Anthropic API / Local LLM
```

## Prerequisites

- **Node.js** 18+ and npm 9+
- **Python** 3.10+

**Platform support:** Tested on Ubuntu 22.04 and Windows. Other Linux distributions are likely compatible but untested. macOS is not yet supported or tested — planned for a future release.

## Quick Start

### 1. Install frontend dependencies

```bash
cd front_end
npm install
```

### 2. Set up the Python virtual environment

```bash
cd back_end
python -m venv nlm_backend_venv
```

Activate it:

```bash
# Windows
nlm_backend_venv\Scripts\activate

# Linux
source nlm_backend_venv/bin/activate
```

Then install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Create the MongoDB credentials file

The backend reads `~/.nlm/mongodb_credentials.env` directly. Create it with:

```bash
# Windows (PowerShell)
New-Item -ItemType Directory -Force "$HOME\.nlm" | Out-Null
'MONGODB_CONNECTION_STRING="mongodb://localhost:27019"' | Set-Content -Encoding utf8 "$HOME\.nlm\mongodb_credentials.env"

# Linux
mkdir -p ~/.nlm
echo 'MONGODB_CONNECTION_STRING="mongodb://localhost:27019"' > ~/.nlm/mongodb_credentials.env
chmod 600 ~/.nlm/mongodb_credentials.env
```

The default URI (`mongodb://localhost:27019`) works with the bundled mongod — no edit needed for local dev. For MongoDB Atlas, replace with your cluster URI. `DATABASE_NAME` is optional and defaults to `nlm_translator`.

### 4. Add Bible source data

The `data/` directory is gitignored. Bible import will not work until USFM source directories are present:

```
data/bibles/
├── eng-web_usfm/    # English World English Bible (base language)
└── bgt_usfm/        # (or other target language USFM directories)
```

Populate these manually from your source files before importing via the app. This step will be automated in a future setup script.

### 5. Launch the app

```bash
cd front_end
npm run dev
```

This starts webpack, Vite, and Electron concurrently. On first run, the `predev` hook downloads a MongoDB binary to `~/.nlm/bin/`. Electron then automatically starts:
1. **MongoDB** (`~/.nlm/bin/mongod` on port 27019)
2. **FastAPI backend** (`python main.py` on port 8221)

All persistent data — the MongoDB database with your imported Bibles, dictionaries, and translation work — lives in `~/.nlm/db/`, outside the repo. Back this directory up if you want to preserve your work across machines or OS reinstalls.

### 6. Configure AI chat (optional)

On first launch, open **Settings > Chat Config** to set your LLM provider:

- **Anthropic**: Enter your API key and select a model (default: `claude-sonnet-4-6`)
- **OpenRouter**: Enter your OpenRouter API key and model identifier (default: `anthropic/claude-sonnet-4.6`)
- **Local LLM**: Set the base URL (default: `http://127.0.0.1:8080`) — requires a local server implementing the Anthropic Messages API (e.g., llama.cpp)

Config is stored at `~/.nlm/chat_config.json` (auto-created with defaults on first use).

## Running Without Electron (Standalone Backend)

Start MongoDB manually, then the backend:

```bash
~/.nlm/bin/mongod --port 27019 --dbpath ~/.nlm/db

cd back_end
source nlm_backend_venv/bin/activate
python main.py
```

The API is available at `http://localhost:8221/api`. Interactive docs at `http://localhost:8221/docs`.

## Running Tests

### Backend

```bash
cd back_end
source nlm_backend_venv/bin/activate
pytest          # All tests
pytest -v       # Verbose
```

Route tests require MongoDB. The test suite auto-starts `mongod` from `~/.nlm/bin/mongod` if it's not already running.

### Frontend

```bash
cd front_end
npm test              # All tests (main + renderer)
npm run test:main     # Main process only
npm run test:renderer # Renderer only
npm run test:coverage # With coverage report
```

## Project Structure

```
back_end/               # FastAPI backend (Python)
|   +-- main.py             # Entry point, 20 route registrations
|   +-- routes/             # REST API handlers
|   +-- shared/             # LLM tool loop, tool registry, chat config
|   +-- utils/              # Parsers, importers, LLM provider
|   +-- mcp_server/         # MCP tools for Claude Code integration
|   +-- db_connector/       # MongoDB async connection (Motor)
|   +-- prompts/            # System prompts and skills
|   +-- tests/              # pytest suite
|   +-- docs/               # Backend documentation
|
+-- front_end/              # Electron + React app (TypeScript)
|   +-- src/main/           # Electron main process
|   +-- src/renderer/       # React app (Vite)
|   +-- src/components/     # Feature viewers (Bible, Dictionary, etc.)
|   +-- docs/               # Frontend documentation
|
+-- data/                   # Bible and dictionary data files
|   +-- bibles/             # USFM and HTML Bible sources
|   +-- dictionaries/       # Language dictionaries
|
+-- local_llm/              # Local LLM setup (llama.cpp)
```

## Documentation

| Area | Location |
|------|----------|
| Backend API Reference | [back_end/docs/api.md](back_end/docs/api.md) |
| Backend Architecture | [back_end/docs/architecture.md](back_end/docs/architecture.md) |
| Chat & AI System | [back_end/docs/chat-system.md](back_end/docs/chat-system.md) |
| Database Schema | [back_end/docs/database.md](back_end/docs/database.md) |
| Configuration | [back_end/docs/configuration.md](back_end/docs/configuration.md) |
| Bible Import | [back_end/docs/import.md](back_end/docs/import.md) |
| MCP Server | [back_end/mcp_server/README.md](back_end/mcp_server/README.md) |
| Frontend Architecture | [front_end/docs/architecture.md](front_end/docs/architecture.md) |
| Frontend Components | [front_end/docs/components.md](front_end/docs/components.md) |
| Local LLM Setup | [local_llm/SETUP.md](local_llm/SETUP.md) |

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Desktop | Electron 39 |
| Frontend | React 18, TypeScript, Material-UI 5 |
| Build | Vite (renderer), Webpack (main process) |
| Backend | FastAPI, Uvicorn, Python 3.10+ |
| Database | MongoDB (bundled binary), Motor async driver |
| AI | Anthropic Claude API, local LLM via llama.cpp |
| MCP | Model Context Protocol server for Claude Code or Claude Desktop/Cowork |
| Tests | pytest (backend), Vitest (frontend) |
