# main.py

import os
import logging
import uuid
from contextvars import ContextVar
from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware

FAST_API_PORT = int(os.getenv('FAST_API_PORT', 8221))

# Set up logging
logging.basicConfig(level=logging.INFO)

request_id_var: ContextVar[str] = ContextVar('request_id', default='--------')

class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True

root_logger = logging.getLogger()
_request_id_filter = RequestIdFilter()
for handler in root_logger.handlers:
    handler.addFilter(_request_id_filter)
    handler.setFormatter(
        logging.Formatter('%(levelname)s:%(name)s:[%(request_id)s] %(message)s')
    )

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="NLM FastAPI Endpoint",
    description="API for New Language Model Bible translation operations",
    version="0.0.1",
    docs_url=None, redoc_url=None, openapi_url=None,
)

# Import routers
from routes.check_connection import router as check_connection_router
from routes.languages import router as languages_router
from routes.bible_books import router as bible_books_router
from routes.new_language import router as new_language_router
from routes.import_bible import router as import_bible_router
from routes.export_bible import router as export_bible_router
from routes.import_html_bible import router as import_html_bible_router
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
app.include_router(import_html_bible_router, prefix="/api")
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