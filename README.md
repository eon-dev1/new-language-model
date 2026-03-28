The New Language Model uses context engineering to facilitate Bible translation. 

The translation cycle will start with any amount of parallel Bible translation, and can also start with an imported dictionary or grammar outline, called Source Materials. (Future imports from Webonary.org are planned)

These Source Materials will each come in to tiers: human-verified, and AI-drafted. The bible, dictionary, and grammar are imported into MongoDB and comes equiped with tools that an AI agent can call to begin assisting translation. 

Example prompt , "Compare parallell translations of Matthew - Luke, and generate a dictionary for words that don't yet have entries". (Quick prompts can be configured to send prompt templates like this) The AI will produce dictionary drafts which the human translator can verify in the GUI. Verified entries have higher confidence scores when feeding them as context for future queries. 

Another example "Create a draft of John 1 - 5 from available data" - the AI will query verses that have parallell translations already, and query the dictionary and grammar documents, giving higher condfidence to human-verified entries. The AI will then make MCP tool calls to update the database with translation drafts. 

**This project is in early development. Expect breaking changes**

Future Plans
- Import/export connection with Paratext and Paranext
- Import connection with Webonary
- One click import of webonary.org dictionaries
- Local LLM integration (not yet fully tested)
- Multi-agent coordination
- Multi-user team-based projects
- Delete, Undo, change history & restore functions

Known Issues
- So far tested only on Ubuntu 24.04, not yet Windows/Mac compatible
- UI is not fully wired up to human-initiated edits
- Memory reading and writing not fully implemented yet

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
- **Python** 3.12+

## Quick Start

### 1. Install frontend dependencies

```bash
cd front_end
npm install
```

### 2. Set up MongoDB credentials

```bash
mkdir -p ~/.nlm
echo 'MONGODB_CONNECTION_STRING="mongodb://localhost:27019"' > ~/.nlm/mongodb_credentials.env
chmod 600 ~/.nlm/mongodb_credentials.env
```

Then update the pointer file at `back_end/db_connector/mongo_credentials_path.env`:

```env
MONGODB_CREDENTIALS_PATH='/home/YOUR_USER/.nlm/mongodb_credentials.env'
DATABASE_NAME='nlm_db'
```

### 3. Install backend dependencies

```bash
cd back_end
python -m venv nlm_backend_venv
source nlm_backend_venv/bin/activate
pip install -r requirements.txt
```

### 4. Launch the app

```bash
cd front_end
npm run dev
```

This starts three npm processes concurrently (webpack watcher, Vite dev server, Electron app). On first run, the `predev` hook downloads a MongoDB binary to `~/.nlm/bin/`. The Electron main process then automatically starts:
1. **MongoDB** (`~/.nlm/bin/mongod` on port 27019)
2. **FastAPI backend** (`python main.py` on port 8221)

### 5. Configure AI chat (optional)

On first launch, open **Settings > Chat Config** in the app to set your LLM provider:

- **Anthropic**: Enter your API key and select a model (default: `claude-sonnet-4-6`)
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
+-- back_end/               # FastAPI backend (Python)
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
+-- __plans__/              # Development planning documents
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
| Backend | FastAPI, Uvicorn, Python 3.12+ |
| Database | MongoDB (bundled binary), Motor async driver |
| AI | Anthropic Claude API, local LLM via llama.cpp |
| MCP | Model Context Protocol server for Claude Code |
| Tests | pytest (backend), Vitest (frontend) |


- Preview:
<img width="1338" height="736" alt="image" src="https://github.com/user-attachments/assets/e2f8c0cd-db8b-4255-8867-68e23a351446" />

<img width="1413" height="736" alt="image" src="https://github.com/user-attachments/assets/6f0cbe2c-4293-4e61-a55b-2ea07eae5451" />

<img width="1221" height="855" alt="image" src="https://github.com/user-attachments/assets/16b44b83-9b0e-4edf-b54d-7fe101d7d963" />


