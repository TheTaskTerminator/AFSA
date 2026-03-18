"""Conversation repository."""
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import ConversationMessage, ConversationSession
from app.repositories.base import BaseRepository
from app.schemas.conversation import MessageCreate, SessionCreate


class ConversationRepository:
    """Conversation repository for database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # Session operations
    async def create_session(
        self, user_id: Optional[UUID] = None, expires_in_seconds: Optional[int] = None
    ) -> ConversationSession:
        """Create a new conversation session."""
        expires_at = None
        if expires_in_seconds is not None:
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)

        session = ConversationSession(
            user_id=user_id,
            status="active",
            expires_at=expires_at,
        )
        self.session.add(session)
        await self.session.flush()
        await self.session.refresh(session)
        return session

    async def get_session(self, session_id: UUID) -> Optional[ConversationSession]:
        """Get a session by ID."""
        result = await self.session.execute(
            select(ConversationSession)
            .options(selectinload(ConversationSession.messages))
            .where(ConversationSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_session_with_messages(
        self, session_id: UUID, message_limit: int = 100
    ) -> tuple[Optional[ConversationSession], List[ConversationMessage]]:
        """Get a session with messages.

        Returns a tuple of (session, messages) to avoid lazy loading issues.
        """
        result = await self.session.execute(
            select(ConversationSession)
            .where(ConversationSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            return None, []

        # Load messages separately with limit
        msg_result = await self.session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.asc())
            .limit(message_limit)
        )
        messages = list(msg_result.scalars().all())
        return session, messages

    async def get_user_sessions(
        self, user_id: UUID, skip: int = 0, limit: int = 20
    ) -> List[ConversationSession]:
        """Get sessions by user."""
        result = await self.session.execute(
            select(ConversationSession)
            .where(ConversationSession.user_id == user_id)
            .order_by(ConversationSession.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def close_session(self, session_id: UUID) -> Optional[ConversationSession]:
        """Close a session."""
        session = await self.get_session(session_id)
        if session is None:
            return None
        session.status = "closed"
        await self.session.flush()
        await self.session.refresh(session)
        return session

    async def expire_session(self, session_id: UUID) -> Optional[ConversationSession]:
        """Expire a session."""
        session = await self.get_session(session_id)
        if session is None:
            return None
        session.status = "expired"
        await self.session.flush()
        await self.session.refresh(session)
        return session

    async def cleanup_expired_sessions(self) -> int:
        """Mark all expired sessions as expired."""
        now = datetime.utcnow()
        result = await self.session.execute(
            select(ConversationSession)
            .where(
                ConversationSession.status == "active",
                ConversationSession.expires_at < now,
            )
        )
        expired = result.scalars().all()
        count = 0
        for session in expired:
            session.status = "expired"
            count += 1
        await self.session.flush()
        return count

    # Message operations
    async def add_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> ConversationMessage:
        """Add a message to a session."""
        message = ConversationMessage(
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata,
        )
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def get_messages(
        self, session_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ConversationMessage]:
        """Get messages for a session."""
        result = await self.session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_messages(
        self, session_id: UUID, limit: int = 20
    ) -> List[ConversationMessage]:
        """Get recent messages for a session."""
        result = await self.session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        return list(reversed(messages))

    async def count_messages(self, session_id: UUID) -> int:
        """Count messages in a session."""
        from sqlalchemy import func

        result = await self.session.execute(
            select(func.count())
            .select_from(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
        )
        return result.scalar_one()