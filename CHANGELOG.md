# Changelog

All notable changes to this project will be documented in this file.

---

## [1.2.0] - 2026-05-07

### Added

- **OpenRouter LLM provider** — a third provider option alongside Anthropic and local, selectable from Chat Settings with its own API key field and model picker
- **OpenAI-compatible provider** (`back_end/utils/openai_provider.py`) — separate ~278-line provider class that handles OpenRouter's Qwen models via `/v1/chat/completions` with explicit `reasoning: {enabled: false}`; routed by `model_registry.get_api_format()`
- **Qwen models in the OpenRouter picker** — `qwen/qwen3.5-397b-a17b` and `qwen/qwen3.5-35b-a3b` (262K context, no thinking, OpenAI wire format)
- **Centralized model registry** (`back_end/shared/model_registry.py`) — single source of truth for context windows, thinking support, display labels, and wire format per model; Anthropic Sonnet/Opus 4.6 entries set to a 1,000,000-token context window
- **Global server-enforced `thinking_enabled` flag** — authoritative toggle in Chat Settings that cannot be bypassed from the frontend or API
- **System-prompt skill composition** — new `load_skill()` and `compose_prompt()` overlay skill definitions onto the base system prompt deterministically
- **`verse-translation` skill** (`back_end/prompts/skills/verse-translation/SKILL.md`) — content loaded by the batch translation route's composed system prompt
- **`TrustedHostMiddleware`** — restricts allowed hosts to `127.0.0.1`/`localhost` for the desktop-bundled API
- **API docs surface disabled** — `/docs`, `/redoc`, `/openapi.json` turned off at the `FastAPI(...)` constructor
- **System prompt expanded** — new "Tool Usage — Building Context for Translation" section in `prompts/system-prompt.md` materially changes Scribe's tool-calling order
- **Memory tools wired into translation** — `search_language_notes` and `search_correction_log` now available during the translation tool loop
- **Translation rate-limit pacing** — `run_tool_loop()` accepts a `pace_seconds` parameter; translation endpoints pass `2.0` for a 2-second sleep between LLM iterations to stay under the 30K TPM tier
- **Tooltip font scales with theme** — `MuiTooltip` override added in `createDynamicTheme.ts`
- **OpenRouter integration documentation** (`back_end/docs/openrouter_docs.md`)
- **Broad new backend test coverage** — model registry, system prompt composition, thinking flag enforcement, and the OpenAI-compat provider
- **New frontend test coverage** — `download-mongo-binaries.test.js`, `ChatDrawerThinkingFlag.test.tsx`, and `ChatModes.test.tsx`

### Added (Windows compatibility)

- **Windows MongoDB binaries** — `download-mongo-binaries.js` now downloads pinned `mongodb-windows-x86_64-8.0.19.zip` and `mongodb-database-tools-windows-x86_64-100.14.0.zip` with their own SHA256 hashes
- **PowerShell `Expand-Archive` extraction path** with tmp directory cleanup in a `finally` block
- **`scripts/wait-file.js`** — replaces `wait-on`, working around Windows `ReadDirectoryChangesW` events that fire with `name === null`
- **`shell.openExternal` IPC bridge** with an https-only allowlist enforced in the main process
- **"AI Thinking" master toggle in Chat Settings** — global switch that hides the thinking-mode bar and forces thinking off at send time
- **"Support" menu item in TopBar** — opens the project support page via the new external-link IPC

### Changed

- **MongoDB credentials simplified to a single `~/.nlm/mongodb_credentials.env`** — *breaking for existing installs*; replaces the previous two-tier pointer-file model. `DATABASE_NAME` is now optional and defaults to `"nlm_translator"`, so installs that previously used a custom DB name (e.g., `nlm_db` from the old README) must carry that value forward or they will silently bind to a different database
- **Translation route refactored** — system prompt is now static (single-verse base or precomposed batch), with all dynamic context moved into the user message; HMAC signing over the batch system prompt is precomputed at import (now vestigial — signs a static server-known constant — but kept for client echo/verify backward compatibility)
- **`AnthropicProvider.is_local` replaced by `provider_type`** — `Literal["anthropic", "local", "openrouter"]`; thinking exclusion and routing now key off this discriminator
- **`THINKING_BETA_HEADER`** set to `"interleaved-thinking-2025-05-14"` for production API compatibility
- **Cross-platform `mongod` binary resolution** — picks `mongod.exe` on win32 and `mongod` elsewhere; `GLIBC_TUNABLES=glibc.pthread.rseq=0` now gated to Linux only
- **API base URL hardcoded to `http://127.0.0.1:8221/api`** — removes the `.env` / `VITE_API_BASE_URL` setup step
- **Python target lowered from 3.12+ to 3.10+** — broader contributor compatibility
- **pytest upgraded** from `8.x` to `9.x` (and `pytest-asyncio` from `0.23.x` to `1.x`)
- **Electron** bumped from `^39.2.4` to `^39.8.9`; **Vite** from `^7.0.4` to `^7.3.2`
- **Frontend version** bumped from `0.2.0` to `1.2.0`
- **SHA256 pinning enforced** — `installBinary()` asserts a 64-char hex hash is configured and verifies the downloaded archive against it before extraction (runs at `npm run prepare:mongo`)
- **Local LLM setup overhauled** — `local_llm/SETUP.md` rewritten into a full clone/build/run guide (~33 → ~107 lines, with Linux/Windows/macOS CUDA/Metal instructions); new `local_llm/local_llm_config.env.example`; `start-server.sh` rewritten to source and validate `NLM_LLAMA_CPP` and `NLM_MODEL_PATH`; default chat template changed to `ibm-granite-4-tiny.jinja`
- **Repo-root `pytest.ini`** — log level raised from `INFO` to `DEBUG`; `integration` marker registered
- **Documentation refresh** — `back_end/docs/*` and `front_end/docs/*` updated alongside the new `back_end/docs/openrouter_docs.md`
- **README rewritten** with Windows PowerShell setup instructions alongside Linux bash; explicitly states "Tested on Ubuntu 22.04 and Windows. macOS not yet supported"

### Removed

- **`back_end/db_connector/mongo_credentials_path.env.example`** — obsolete with the single-file credentials model
- **`back_end/pytest.ini`** — consolidated into the repo-root `pytest.ini`; pytest must now be invoked from the repo root
- **Obsolete credentials-path test class** in `test_imports_and_structure.py` — replaced by the new home-directory-based test suite
- **`wait-on` dependency** — replaced by in-tree `scripts/wait-file.js`
- **`scripts/download-mongod.js`** — superseded Linux-only downloader, now removed
- **Renderer-side "Show Console Log" menu item and its custom DevTools IPC handler** — replaced by Electron's built-in `toggleDevTools` role; `devtools-manager.ts` itself remains and still drives auto-open behavior from the saved startup preference
- **`repository` field from `front_end/package.json`**

### Fixed (Windows compatibility)

- **Explicit UTF-8 encoding on file I/O** across chat config, MCP tool result writes, and tests (the credentials reader uses `utf-8-sig` to tolerate a BOM) — prevents silent corruption from Windows' default `cp1252` codec on non-Latin Bible text
- **`mongodump` binary selection on Windows** (`mongodump.exe`) and skipped POSIX `os.chmod(0o400)` on win32
- **HTTPX test client base URL** changed to `http://localhost` so route tests pass through the new `TrustedHostMiddleware`

### Security

- **TrustedHost binding** — closes host-header spoofing on the desktop-bundled API port
- **API docs surface disabled** — `/docs`, `/redoc`, `/openapi.json` turned off, removing unintended endpoint enumeration
- **External link opener restricted to https://** — blocks `file://`, `javascript:`, etc. from the renderer
- **Windows MongoDB downloads SHA256-pinned** — supply-chain integrity for the new download path

---

## [0.2.0] - 2026-03-27

### Infrastructure

- **Removed Docker** in favor of a bundled MongoDB binary managed directly by the Electron main process — no external install or Docker setup required
- **Replaced MCP-based communication** with direct REST API calls between the frontend and FastAPI backend
- **Beginning local LLM support** — initial scaffolding and setup scripts for running a local LLM server as an alternative to the Anthropic API (not yet fully tested)

### Added

- **In-app chat system** — a persistent chat drawer with conversation history, context management, and per-project chat sessions
- **Tool approval UI** — users can review and approve or deny AI tool calls before they execute
- **Skills system** — prompt-based skills including a translation roundtable, translation triologue, and dictionary entry generation
- **LLM provider abstraction** — backend now supports multiple LLM providers (Anthropic API and local models) via a unified provider interface
- **Batch translation** — translate multiple verses in a single operation
- **Verse selection toolbar** — select and act on ranges of verses directly in the Bible reader
- **Word index** — tokenizer and index builder for word-level search and lookup, exposed as both an API route and MCP tool
- **Correction log** — track and review translation corrections over time
- **Notes tab** — per-project notes panel
- **Export Bible route** — export translated Bible content (note: not yet tested with cross-references, footnotes, etc.)
- **Load base language route** — dedicated endpoint for loading a base language dataset
- **MongoDB backup** — database backup route for exporting and preserving project data

### Changed

- **Grammar renamed to Memories** — the grammar tab and all related backend routes, MCP tools, and data structures have been renamed to "Memories" to better reflect intended usage
- **LLM config moved to `~/.nlm/chat_config.json`** — provider, API key, and model settings are now stored in the user's home directory outside the repository; no `.env` file needed for LLM configuration
- **Extended thinking** — supported on Anthropic Sonnet and Opus models; automatically disabled for local LLMs and Haiku
- **Write tool approval with inline editing** — when the AI proposes a write operation (e.g. dictionary or memories update), the stream pauses and the user can review, edit, and approve or reject before execution resumes

### Developer

- Added Enoch JSON → USFM conversion utility — a niche developer tool for POC testing on medium-resource languages that already have a New Testament translation or more; not relevant for most use cases
- **`npm run prepare:mongo` required on first setup** — downloads bundled MongoDB binaries; runs automatically via `predev` hook before `npm run dev`
- **New test suites** — added coverage for chat system, tool registry, word index, memories, correction log, and database backup (including credential leak verification)

---

## [0.0.1] - 2026-01-05

Initial public release.
