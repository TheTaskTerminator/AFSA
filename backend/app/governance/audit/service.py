"""Audit service for tracking all actions."""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.schemas.audit import AuditResult


class AuditService:
    """Service for recording and querying audit logs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(
        self,
        action: str,
        resource: str,
        result: AuditResult,
        actor_user_id: Optional[UUID] = None,
        actor_username: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor_ip_address: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        changes: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        snapshot_id: Optional[str] = None,
    ) -> AuditLog:
        """Record an audit log entry."""
        log = AuditLog(
            timestamp=datetime.utcnow(),
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            actor_role=actor_role,
            actor_ip_address=actor_ip_address,
            action=action,
            resource=resource,
            resource_id=resource_id,
            changes=changes,
            result=result.value,
            error_message=error_message,
            context=context,
            snapshot_id=snapshot_id,
        )
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log

    async def log_success(
        self,
        action: str,
        resource: str,
        actor_user_id: Optional[UUID] = None,
        actor_username: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor_ip_address: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        changes: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        snapshot_id: Optional[str] = None,
    ) -> AuditLog:
        """Record a successful action."""
        return await self.log(
            action=action,
            resource=resource,
            result=AuditResult.SUCCESS,
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            actor_role=actor_role,
            actor_ip_address=actor_ip_address,
            resource_id=resource_id,
            changes=changes,
            context=context,
            snapshot_id=snapshot_id,
        )

    async def log_failure(
        self,
        action: str,
        resource: str,
        error_message: str,
        actor_user_id: Optional[UUID] = None,
        actor_username: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor_ip_address: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        changes: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Record a failed action."""
        return await self.log(
            action=action,
            resource=resource,
            result=AuditResult.FAILURE,
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            actor_role=actor_role,
            actor_ip_address=actor_ip_address,
            resource_id=resource_id,
            changes=changes,
            error_message=error_message,
            context=context,
        )

    async def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        actor_user_id: Optional[UUID] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        result: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Query audit logs with filters."""
        query = select(AuditLog)

        if start_time:
            query = query.where(AuditLog.timestamp >= start_time)
        if end_time:
            query = query.where(AuditLog.timestamp <= end_time)
        if actor_user_id:
            query = query.where(AuditLog.actor_user_id == actor_user_id)
        if action:
            query = query.where(AuditLog.action == action)
        if resource:
            query = query.where(AuditLog.resource == resource)
        if result:
            query = query.where(AuditLog.result == result)

        query = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)

        result_obj = await self.session.execute(query)
        return list(result_obj.scalars().all())

    async def get_log(self, log_id: UUID) -> Optional[AuditLog]:
        """Get a specific audit log."""
        result = await self.session.execute(
            select(AuditLog).where(AuditLog.id == log_id)
        )
        return result.scalar_one_or_none()

    async def count_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        actor_user_id: Optional[UUID] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        result: Optional[str] = None,
    ) -> int:
        """Count audit logs with filters."""
        from sqlalchemy import func

        query = select(func.count()).select_from(AuditLog)

        if start_time:
            query = query.where(AuditLog.timestamp >= start_time)
        if end_time:
            query = query.where(AuditLog.timestamp <= end_time)
        if actor_user_id:
            query = query.where(AuditLog.actor_user_id == actor_user_id)
        if action:
            query = query.where(AuditLog.action == action)
        if resource:
            query = query.where(AuditLog.resource == resource)
        if result:
            query = query.where(AuditLog.result == result)

        result_obj = await self.session.execute(query)
        return result_obj.scalar_one()