"""Chat API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.chat.models import ChatRequest, ChatResponse
from app.chat.service import ChatService
from app.db import get_db
from app.market import PriceCache


def create_chat_router(price_cache: PriceCache) -> APIRouter:
    """Create the chat API router with price cache dependency."""

    router = APIRouter(prefix="/api/chat", tags=["chat"])
    service = ChatService(price_cache)

    @router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
    async def send_message(request: ChatRequest) -> ChatResponse:
        """Send a message to the AI trading assistant.

        The LLM may auto-execute trades or modify the watchlist based on the conversation.

        - Message must be 1-1000 characters
        - Returns assistant response with any executed actions
        """
        db = get_db()
        db.init_db()

        try:
            return await service.send_message(request.message, user_id="default")

        except ValueError as e:
            # Business logic validation errors
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            # Log the actual exception for debugging
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process chat message: {type(e).__name__}: {str(e)}",
            )

    return router
