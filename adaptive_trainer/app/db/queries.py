from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationMode


async def get_active_convo(db: AsyncSession, phone: str) -> Conversation | None:
    """Return the most-recently-updated non-onboarding conversation, or None."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.phone_number == phone)
        .where(Conversation.mode != ConversationMode.onboarding)
        .order_by(Conversation.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
