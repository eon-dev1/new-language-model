# NLM Backend 

- `utils/schema_enforcer/schema_definition.py` - Single source of truth for MongoDB schema
- The app bundles and manages its own MongoDB. It is not a system service.
- `mongod` runs with `--auth`. The credential (`~/.nlm/mongodb_credentials.env`) is created once by `python -m db_connector.setup_auth` (run by `npm run setup`); the app only verifies enforcement at startup (`db_connector/auth_probe.py`) and never creates or repairs users.
- `mongod` is spawned by two independent processes sharing `~/.nlm/db`: Electron (`front_end/src/main/mongod-manager.ts`) and the pytest session fixture (`tests/conftest.py`). Both must spawn with `--auth`, and both verify enforcement after startup.
