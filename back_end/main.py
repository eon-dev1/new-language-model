# main.py

import os
import logging
import uuid
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError

from db_connector.auth_probe import AuthEnforcementError, verify_auth_enforced
from db_connector.connection import get_mongodb_connector
from utils.schema_enforcer.enforcer import SchemaEnforcer
from shared.logging_setup import install_logging, request_id_var

FAST_API_PORT = int(os.getenv('FAST_API_PORT', 8221))

install_logging()

logger = logging.getLogger(__name__)

# Exceeding this is fatal, so it errs generous: covers the 5s
# serverSelectionTimeoutMS plus overhead for one connection and one command.
AUTH_BUDGET_S = 6
# Exceeding this is non-fatal, so it errs tight: schema enforcement measures
# at ~0.1s warm against the real dbpath.
ENFORCE_BUDGET_S = 15
# INV: 2 * AUTH_BUDGET_S + ENFORCE_BUDGET_S < backend-manager.ts's
# MAX_RETRIES(30) * RETRY_INTERVAL(1s) = 30 — see test_auth_budget_invariant.py.

MIGRATION_MESSAGE = (
    "MongoDB now requires authentication, but ~/.nlm/mongodb_credentials.env has no\n"
    "password. Your data is intact — this only affects access. To create a credential:\n"
    "\n"
    "  cd back_end && source nlm_backend_venv/bin/activate\n"
    "  python -m db_connector.setup_auth\n"
    "\n"
    "(Windows: nlm_backend_venv\\Scripts\\activate)"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auth gate — two propositions, both fatal:
    #   (a) does mongod enforce auth at all?      (anonymous probe)
    #   (b) does OUR stored credential work?      (authenticated connect)
    # A timeout here means the verdict is UNKNOWN, and unknown must fail closed.
    # Do NOT widen these except clauses — asyncio.TimeoutError is builtins.TimeoutError
    # ⊂ OSError ⊂ Exception, so a bare `except Exception` silently swallows the verdict
    # and the server binds with auth possibly off.
    connector = None
    try:
        await asyncio.wait_for(asyncio.to_thread(verify_auth_enforced), AUTH_BUDGET_S)
        connector = await asyncio.wait_for(get_mongodb_connector(), AUTH_BUDGET_S)
    except AuthEnforcementError:
        raise  # fatal — no HTTP server binds
    except asyncio.TimeoutError as e:
        raise AuthEnforcementError("auth verification did not reach a verdict") from e
    except OperationFailure as e:
        if e.code in (13, 18):  # our credential is absent/stale
            raise AuthEnforcementError(MIGRATION_MESSAGE) from e
        raise  # unknown auth code — fail closed
    except (ConnectionFailure, ServerSelectionTimeoutError):
        pass  # mongod down — existing path, connector stays None

    # Anything not named above propagates and is fatal — by design, not by
    # omission: an import error, a driver bug, a malformed URI — none of
    # those are the exceptions above, so they escape and no server binds.

    if connector is not None:
        try:
            report = await asyncio.wait_for(
                SchemaEnforcer(connector, dry_run=False).enforce(), ENFORCE_BUDGET_S
            )
            logger.info(report.summary())
        except Exception as e:  # schema enforcement genuinely is non-fatal
            logger.error(f"schema enforcement failed at startup (non-fatal): {e}")
    yield


# Initialize FastAPI app
app = FastAPI(
    title="NLM FastAPI Endpoint",
    description="API for New Language Model Bible translation operations",
    version="0.0.1",
    docs_url=None, redoc_url=None, openapi_url=None,
    lifespan=lifespan,
)

# Import routers
from routes.check_connection import router as check_connection_router
from routes.languages import router as languages_router
from routes.bible_books import router as bible_books_router
from routes.new_language import router as new_language_router
from routes.import_bible import router as import_bible_router
from routes.export_bible import router as export_bible_router
from routes.bible_reader import router as bible_reader_router
from routes.dictionary import router as dictionary_router
from routes.grammar import router as grammar_router
from routes.chat_config import router as chat_config_router
from routes.chat import router as chat_router
from routes.chat_conversations import router as chat_conversations_router
from routes.chat_skills import router as chat_skills_router
from routes.word_index import router as word_index_router
from routes.load_base_language import router as load_base_language_router
from routes.translate import router as translate_router
from routes.memories import router as memories_router
from routes.correction_log import router as correction_log_router
from routes.db_backup import router as db_backup_router

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    return response

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["127.0.0.1", "localhost"],
)

# Register routes
app.include_router(check_connection_router, prefix="/api")
app.include_router(languages_router, prefix="/api")
app.include_router(bible_books_router, prefix="/api")
app.include_router(new_language_router, prefix="/api")
app.include_router(import_bible_router, prefix="/api")
app.include_router(export_bible_router, prefix="/api")
app.include_router(bible_reader_router, prefix="/api")
app.include_router(dictionary_router, prefix="/api")
app.include_router(grammar_router, prefix="/api")
app.include_router(chat_config_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(chat_conversations_router, prefix="/api")
app.include_router(chat_skills_router, prefix="/api")
app.include_router(word_index_router, prefix="/api")
app.include_router(load_base_language_router, prefix="/api")
app.include_router(translate_router, prefix="/api")
app.include_router(memories_router, prefix="/api")
app.include_router(correction_log_router, prefix="/api")
app.include_router(db_backup_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on localhost:{FAST_API_PORT}")
    uvicorn.run(
        app,
        host="127.0.0.1",  # Only localhost
        port=FAST_API_PORT,
        log_level="info"
    )