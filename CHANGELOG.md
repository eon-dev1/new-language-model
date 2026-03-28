# Changelog

All notable changes to this project will be documented in this file.

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
