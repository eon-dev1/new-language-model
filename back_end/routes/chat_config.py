"""
Chat configuration API endpoints.

GET  /chat/config           - Get current config (API key masked)
POST /chat/config           - Update config settings
POST /chat/test-connection  - Test LLM provider connectivity
"""

import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from shared.chat_config import get_public_config, update_config
from utils.llm_provider import get_provider, ProviderConfigError

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatConfigUpdate(BaseModel):
    llm_provider: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    openrouter_model: Optional[str] = None
    local_base_url: Optional[str] = None
    local_model: Optional[str] = None
    thinking_enabled: Optional[bool] = None


@router.get("/chat/config")
async def get_config():
    """Get current chat configuration (API key masked)."""
    return get_public_config()


@router.post("/chat/config")
async def post_config(config: ChatConfigUpdate):
    """Update chat configuration."""
    updates = {k: v for k, v in config.model_dump().items() if v is not None}
    update_config(updates)
    return get_public_config()


@router.post("/chat/test-connection")
async def test_connection():
    """Test that the configured LLM provider is reachable and working."""
    try:
        provider = get_provider()
    except ProviderConfigError as e:
        return {"success": False, "error": str(e)}

    try:
        async for event in provider.stream_chat(
            messages=[{"role": "user", "content": "Say 'ok'"}],
            system_prompt="Respond with only 'ok'.",
            tools=None,
            max_tokens=10,
        ):
            if event.get("type") == "error":
                return {"success": False, "error": event.get("content", "Unknown error")}
            if event.get("type") == "text":
                return {"success": True}
            if event.get("type") == "done":
                return {"success": True}
        return {"success": True}
    except Exception:
        logger.exception("Test connection failed")
        return {"success": False, "error": "Connection test failed"}
