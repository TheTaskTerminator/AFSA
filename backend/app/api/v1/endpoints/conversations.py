"""Conversation management endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.conversation import ConversationMessage, ConversationSession
from app.repositories.conversation import ConversationRepository
from app.schemas.conversation import (
    MessageCreate,
    MessageRead,
    MessageRole,
    SessionCreate,
    SessionRead,
    SessionStatus,
    SessionSummary,
)
from app.agents.pm_agent.agent import PMAgent

router = APIRouter()


def _message_to_read(msg: ConversationMessage) -> MessageRead:
    """Convert ConversationMessage model to MessageRead schema."""
    return MessageRead(
        id=msg.id,
        session_id=msg.session_id,
        role=MessageRole(msg.role),
        content=msg.content,
        metadata=msg.msg_metadata,
        created_at=msg.created_at,
    )


def _session_to_read(session: ConversationSession, messages: Optional[List[ConversationMessage]] = None) -> SessionRead:
    """Convert ConversationSession model to SessionRead schema."""
    if messages is None:
        messages = []
    msg_list = [_message_to_read(m) for m in messages]
    return SessionRead(
        id=session.id,
        user_id=session.user_id,
        status=SessionStatus(session.status),
        created_at=session.created_at,
        updated_at=session.updated_at,
        expires_at=session.expires_at,
        messages=msg_list,
    )


def _session_to_summary(session: ConversationSession, message_count: int = 0) -> SessionSummary:
    """Convert ConversationSession model to SessionSummary schema."""
    return SessionSummary(
        id=session.id,
        user_id=session.user_id,
        status=SessionStatus(session.status),
        created_at=session.created_at,
        updated_at=session.updated_at,
        expires_at=session.expires_at,
        message_count=message_count,
    )


async def get_conversation_repo(db: AsyncSession = Depends(get_db)) -> ConversationRepository:
    """Get conversation repository dependency."""
    return ConversationRepository(db)


# Global PM Agent instance (can be made configurable per session)
_pm_agent: Optional[PMAgent] = None


def get_pm_agent() -> PMAgent:
    """Get or create PM Agent instance."""
    global _pm_agent
    if _pm_agent is None:
        _pm_agent = PMAgent()
    return _pm_agent


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    session_create: SessionCreate = SessionCreate(),
    repo: ConversationRepository = Depends(get_conversation_repo),
    db: AsyncSession = Depends(get_db),
) -> SessionRead:
    """Create a new conversation session.

    Creates a new conversation session for multi-turn dialogue with the PM Agent.
    Optionally associates with a user and sets expiration time.
    """
    session = await repo.create_session(
        user_id=session_create.user_id,
        expires_in_seconds=session_create.expires_in_seconds,
    )
    await db.commit()
    await db.refresh(session)

    return _session_to_read(session, messages=[])


@router.get("", response_model=List[SessionSummary])
async def list_conversations(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    status: Optional[SessionStatus] = Query(None, description="Filter by session status"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip"),
    repo: ConversationRepository = Depends(get_conversation_repo),
) -> List[SessionSummary]:
    """List conversation sessions with optional filtering.

    Returns a summary of sessions without loading all messages.
    """
    if user_id:
        sessions = await repo.get_user_sessions(user_id, skip=offset, limit=limit)
    else:
        # Get all sessions (would need additional method in repo)
        sessions = []

    # Filter by status if specified
    if status and sessions:
        sessions = [s for s in sessions if s.status == status.value]

    summaries = []
    for s in sessions:
        count = await repo.count_messages(s.id)
        summaries.append(_session_to_summary(s, count))

    return summaries


@router.get("/{session_id}", response_model=SessionRead)
async def get_conversation(
    session_id: UUID,
    repo: ConversationRepository = Depends(get_conversation_repo),
) -> SessionRead:
    """Get conversation by session ID.

    Returns the session details including all messages.
    """
    session, messages = await repo.get_session_with_messages(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session not found: {session_id}",
        )

    # Check if session is expired
    if session.status == SessionStatus.EXPIRED.value:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Conversation session has expired",
        )

    return _session_to_read(session, messages=messages)


@router.post("/{session_id}/messages", response_model=MessageRead)
async def send_message(
    session_id: UUID,
    message: MessageCreate,
    repo: ConversationRepository = Depends(get_conversation_repo),
    db: AsyncSession = Depends(get_db),
) -> MessageRead:
    """Send a message in a conversation.

    Processes the message through the PM Agent and returns the agent's response.
    The response is stored as an assistant message.
    """
    # Get session
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session not found: {session_id}",
        )

    # Check session status
    if session.status != SessionStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot send message to {session.status} session",
        )

    # Store user message
    user_msg = await repo.add_message(
        session_id=session_id,
        role=MessageRole.USER.value,
        content=message.content,
        metadata=message.metadata,
    )

    # Process through PM Agent
    pm_agent = get_pm_agent()
    agent_response = await pm_agent.process_message(
        session_id=str(session_id),
        message=message.content,
        context=message.metadata,
    )

    # Store assistant response
    assistant_msg = await repo.add_message(
        session_id=session_id,
        role=MessageRole.ASSISTANT.value,
        content=agent_response.content,
        metadata={
            "success": agent_response.success,
            "clarification_questions": agent_response.clarification_questions,
            "has_task_card": agent_response.task_card is not None,
        },
    )

    await db.commit()
    await db.refresh(assistant_msg)

    return _message_to_read(assistant_msg)


@router.get("/{session_id}/messages", response_model=List[MessageRead])
async def get_messages(
    session_id: UUID,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    repo: ConversationRepository = Depends(get_conversation_repo),
) -> List[MessageRead]:
    """Get messages from a conversation session.

    Returns messages in chronological order.
    """
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session not found: {session_id}",
        )

    messages = await repo.get_messages(session_id, skip=offset, limit=limit)
    return [_message_to_read(m) for m in messages]


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_conversation(
    session_id: UUID,
    repo: ConversationRepository = Depends(get_conversation_repo),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Close a conversation session.

    Marks the session as closed. Closed sessions cannot receive new messages.
    """
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session not found: {session_id}",
        )

    if session.status == SessionStatus.CLOSED.value:
        return  # Already closed

    await repo.close_session(session_id)
    await db.commit()

    # Clear PM Agent session state
    pm_agent = get_pm_agent()
    pm_agent.clear_session(str(session_id))


@router.post("/{session_id}/task-card")
async def generate_task_card(
    session_id: UUID,
    repo: ConversationRepository = Depends(get_conversation_repo),
    db: AsyncSession = Depends(get_db),
):
    """Generate a task card from the conversation.

    Analyzes the conversation and generates a structured task card.
    Requires sufficient context from the dialogue.
    """
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session not found: {session_id}",
        )

    if session.status != SessionStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only generate task card from active session",
        )

    # Generate task card via PM Agent
    pm_agent = get_pm_agent()
    task_card = await pm_agent.generate_task_card(str(session_id))

    if task_card is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient context to generate task card. Please provide more details.",
        )

    return {
        "task_card": {
            "id": task_card.id,
            "type": task_card.type,
            "priority": task_card.priority,
            "description": task_card.description,
            "structured_requirements": task_card.structured_requirements,
            "constraints": task_card.constraints,
        },
        "session_id": str(session_id),
    }


@router.get("/{session_id}/state")
async def get_session_state(
    session_id: UUID,
    repo: ConversationRepository = Depends(get_conversation_repo),
):
    """Get the current state of a conversation session.

    Returns information about the session state including
    message count and task card status.
    """
    session = await repo.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session not found: {session_id}",
        )

    # Get PM Agent session state
    pm_agent = get_pm_agent()
    agent_state = pm_agent.get_session_state(str(session_id))

    message_count = await repo.count_messages(session_id)

    return {
        "session_id": str(session_id),
        "status": session.status,
        "message_count": message_count,
        "agent_state": agent_state,
    }