# NLM Bible Translation Platform

A desktop application for managing Bible translation projects in low-resource languages. Built with Electron, React, FastAPI, and MongoDB, with AI-assisted translation via Openrouter or local LLMs.

Translators work through a three-resource model per language: **Bible texts** (verse-by-verse with human verification), **Dictionary** (building a lexicon as you translate), and **Memories** (grammar notes, language observations, correction history). An integrated chat interface connects to Openrouter or a local LLM for context-aware translation assistance with tool use.


## Prerequisites

- **Node.js** 18+ and npm 9+
- **Python** 3.10+ — on Windows, check "Add python.exe to PATH" during install, or `winget install Python.Python.3.12`

**Platform support:** Tested on Ubuntu, Windows and Mac ARM. MacOS Builds are unsigned — if Gatekeeper blocks the bundled mongod on a Mac (rare; binaries from `fastdl.mongodb.org` are not quarantined when downloaded by Node), run `xattr -dr com.apple.quarantine ~/.nlm/bin/`. Intel Macs have not been tested. 

## Quick Start (Linux)

```bash
git https://github.com/eon-dev1/new-language-model.git && cd <repo>
cd front_end
npm run setup
npm run dev
```

`npm run setup` bootstraps a fresh machine with these steps:

1. `npm install` (frontend dependencies)
2. Python virtual environment at `back_end/nlm_backend_venv/`
3. `pip install -r requirements.txt`
4. MongoDB binaries (`mongod` + `mongodump`, ~150 MB) into `~/.nlm/bin/`
5. The MongoDB credential — spawns `mongod`, creates the `nlm_app` database user, and writes `~/.nlm/mongodb_credentials.env` with a generated password

It is safe to re-run: each stage is idempotent. If the credential already exists and works, setup reports "Already configured" and changes nothing.

Then add your Bible source data (see below) and launch with `npm run dev` or `npm start`.

### Add Bible source data

The `data/` directory is gitignored. Bible import will not work until USFM source directories are present:

```
data/bibles/
├── eng-web_usfm/     # English World English Bible (base language)
└── languagecode_usfm/  # (or other target language USFM directories) see https://ebible.org/find.php
```

Populate these manually before importing via the app.

### Launch

```bash
cd front_end
npm run dev
```

This starts webpack, Vite, and Electron concurrently. The `predev` hook re-checks the MongoDB binaries (a no-op after setup). Electron then automatically starts:

1. **MongoDB** (`~/.nlm/bin/mongod` on port 27019, with authentication enforced)
2. **FastAPI backend** (`python main.py` on port 8221)

All persistent data — the MongoDB database with your imported Bibles, dictionaries, and translation work — lives in `~/.nlm/db/`, outside the repo. Back this directory up to preserve your work across machines or OS reinstalls.

### Configure AI chat

On first launch, open **Settings > Chat Config** to set your LLM provider:

- **OpenRouter**: your OpenRouter API key and model identifier - Recommended to enforce Zero Data Retention only providers/models in your OpenRouter settings. 
- **Local LLM**: the base URL (default: `http://127.0.0.1:8080`) — requires a local server implementing the Anthropic Messages API - tested with llama.cpp 

Config is stored at `~/.nlm/chat_config.json` (auto-created with defaults on first use).

## Manual setup (macOS, or Windows fallback)

Use this when the automated `npm run setup` is unavailable or fails partway. Each step is what a stage of `npm run setup` does.

```bash
# 1. Frontend dependencies
cd front_end && npm install

# 2. Python virtual environment
cd ../back_end
python3 -m venv nlm_backend_venv

#    Activate it:
source nlm_backend_venv/bin/activate      # Linux / macOS
#    nlm_backend_venv\Scripts\activate    # Windows (PowerShell)

# 3. Backend dependencies
pip install -r requirements.txt

# 4. MongoDB binaries
cd ../front_end && npm run prepare:mongo

# 5. Create the MongoDB credential
cd ../back_end && python -m db_connector.setup_auth

# 6. Wire the pre-commit secret-scan hook
cd .. && git config core.hooksPath .githooks

# 7. Launch
cd front_end && npm run dev
```

Step 5 spawns `mongod`, creates the `nlm_app` user, and writes `~/.nlm/mongodb_credentials.env`. Do not launch the app while it runs — it prints a warning to that effect and stops the temporary `mongod` when it finishes.

## Upgrading an existing install

Earlier versions ran MongoDB **without authentication**. This version enforces it. After `git pull`:

- Your **data is intact** — enabling authentication changes *access*, not the stored data.
- The old passwordless `~/.nlm/mongodb_credentials.env` no longer works, so the backend refuses to start until a credential exists, printing:

  ```
  MongoDB now requires authentication, but ~/.nlm/mongodb_credentials.env has no
  password. Your data is intact — this only affects access. To create a credential:

    cd back_end && source nlm_backend_venv/bin/activate
    python -m db_connector.setup_auth
  ```

  (Windows: `nlm_backend_venv\Scripts\activate`.)

Running that one command creates the user against your existing database and writes a working credential. **Back up first**.

## The credentials file

`~/.nlm/mongodb_credentials.env` is generated by `setup_auth`.

| Variable | Description |
|----------|-------------|
| `MONGODB_CONNECTION_STRING` | Full connection URI, including the generated password |
| `DATABASE_NAME` | Target database (default `nlm_translator`) |

It holds a **live password** — do not commit or share it. It is stored at mode `0600` outside the repository. The backend, the test suite, and the MCP server all read it; there is no other credential channel.

## Recovering a lost credential

If the file is lost or the database and file disagree, recovery is **manual by design** (an automated self-heal would let anyone delete the file to force the database back into no-auth mode):

1. Stop the app. Start `mongod` **without** `--auth` on the same dbpath:
   `~/.nlm/bin/mongod --port 27019 --dbpath ~/.nlm/db`
2. Drop the existing users from the `admin` database.
3. Stop `mongod`, then re-run `python -m db_connector.setup_auth`.

## Running Without Electron (Standalone Backend)

A credential must already exist (run `npm run setup` or `python -m db_connector.setup_auth` once). Then start MongoDB with authentication, and the backend:

```bash
~/.nlm/bin/mongod --port 27019 --dbpath ~/.nlm/db --auth

cd back_end && source nlm_backend_venv/bin/activate
python main.py
```

The API is available at `http://localhost:8221/api`. Interactive docs at `http://localhost:8221/docs`.

## Secret scanning

`npm run setup` wires a pre-commit hook (`git config core.hooksPath .githooks`) that scans
staged changes with [TruffleHog](https://github.com/trufflesecurity/trufflehog#installation)
and blocks the commit on a hit. If you skipped `npm run setup`, are on macOS, or set up from
a downloaded archive instead of a clone, wire it manually:

```bash
git config core.hooksPath .githooks
```

TruffleHog must be installed — commits are blocked until it is. Deliberate bypass:
`git commit --no-verify`. This is local only; there is no CI gate yet.

A full-history audit (manual, not run automatically) is available at
`ci/secrets_detector/secret-scan-full.sh`.

This is a heuristic offline backstop, not a guarantee: it can miss some credential shapes
(including, occasionally, a MongoDB URI, and almost always a bare password with no URI
context). The real safeguard is that live credentials live in `~/.nlm/`, outside the repo.

## Running Tests

### Backend

```bash
cd back_end
source nlm_backend_venv/bin/activate
pytest          # All tests
pytest -v       # Verbose
```

The suite auto-starts `mongod --auth` from `~/.nlm/bin/mongod` if it isn't already running, and verifies authentication is enforced before running. **It requires `setup_auth` to have run** — on a fresh clone with no credential, tests that touch the database surface the same migration guidance shown above.

### Frontend

```bash
cd front_end
npm test              # All tests (main + renderer)
npm run test:main     # Main process only
npm run test:renderer # Renderer only
npm run test:coverage # With coverage report
```

## Troubleshooting

### `python -m venv` fails with "ensurepip is not available"

Your Python is missing the venv module. Debian/Ubuntu: `sudo apt install python3-venv`.

### `pip install` fails building a package

Likely a missing compiler. Linux: `sudo apt install build-essential libffi-dev`. Windows: install the Build Tools for Visual Studio.

### Windows: PowerShell blocks the activate script

Set the execution policy for your user: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Linux: Electron aborts on launch with a `chrome-sandbox` SUID error

`npm run dev` exits immediately with:

```
FATAL:sandbox/linux/suid/client/setuid_sandbox_host.cc:166] The SUID sandbox
helper binary was found, but is not configured correctly.
```
npm extracts `chrome-sandbox` as your own user, but Electron's setuid sandbox helper must be owned by root with the setuid bit set. Fix it per checkout:

```bash
sudo chown root:root front_end/node_modules/electron/dist/chrome-sandbox
sudo chmod 4755 front_end/node_modules/electron/dist/chrome-sandbox
```

Repeat after any `npm install` that reinstalls or upgrades Electron, since extraction resets the ownership.

The confusing part: the `npm start` command often succeeds from the VS Code integrated terminal and fails from a normal one. Electron prefers a user-namespace sandbox and only falls back to the setuid helper when namespaces are unavailable. Ubuntu 24.04 sets `kernel.apparmor_restrict_unprivileged_userns=1`, allowing unprivileged user namespaces only for processes under an AppArmor profile that grants `userns`. VS Code's profile (`/etc/apparmor.d/code`) grants it and child processes inherit that confinement, so the helper is never consulted and the broken ownership stays hidden. A plain terminal runs unconfined, so Electron takes the fallback path and aborts.

Avoid the two fixes commonly suggested online: `--no-sandbox` disables Electron's renderer sandbox, and `kernel.apparmor_restrict_unprivileged_userns=0` disables a system-wide protection. Both trade away a working security boundary to avoid a one-line ownership fix.

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Desktop | Electron 39 |
| Frontend | React 18, TypeScript  |
| Build | Vite (renderer), Webpack (main process) |
| Backend | FastAPI, Uvicorn, Python 3.10+ |
| Database | MongoDB (bundled binary, authentication enforced), Motor async driver |
| AI | OpenRouter, local LLM via llama.cpp |
| MCP | Model Context Protocol |
| Tests | pytest (backend), Vitest (frontend) |
