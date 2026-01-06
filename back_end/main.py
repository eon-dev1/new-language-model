# main.py

import os
import logging
from fastapi import FastAPI

FAST_API_PORT = int(os.getenv('FAST_API_PORT', 8221))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="NLM FastAPI Endpoint",
    description="API for New Language Model Bible translation operations",
    version="0.0.1"
)

# Import routers
from routes.check_connection import router as check_connection_router
from routes.languages import router as languages_router
from routes.bible_books import router as bible_books_router
from routes.new_language import router as new_language_router
from routes.import_bible import router as import_bible_router
from routes.import_html_bible import router as import_html_bible_router
from routes.bible_reader import router as bible_reader_router
from routes.dictionary import router as dictionary_router
from routes.grammar import router as grammar_router

# Register routes
app.include_router(check_connection_router, prefix="/api")
app.include_router(languages_router, prefix="/api")
app.include_router(bible_books_router, prefix="/api")
app.include_router(new_language_router, prefix="/api")
app.include_router(import_bible_router, prefix="/api")
app.include_router(import_html_bible_router, prefix="/api")
app.include_router(bible_reader_router, prefix="/api")
app.include_router(dictionary_router, prefix="/api")
app.include_router(grammar_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on localhost:{FAST_API_PORT}")
    uvicorn.run(
        app,
        host="127.0.0.1",  # Only localhost
        port=FAST_API_PORT,
        log_level="info"
    )