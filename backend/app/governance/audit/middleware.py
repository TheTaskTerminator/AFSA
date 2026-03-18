"""Audit middleware for automatic request logging."""
import time
from typing import Callable, Optional
from uuid import UUID

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.governance.audit.service import AuditService
from app.schemas.audit import AuditResult


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic audit logging."""

    # Paths to exclude from audit logging
    EXCLUDED_PATHS = {
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    # Actions mapping for HTTP methods
    METHOD_ACTIONS = {
        "GET": "read",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }

    def __init__(
        self,
        app: ASGIApp,
        get_session: Callable,
        get_current_user: Optional[Callable] = None,
    ):
        super().__init__(app)
        self.get_session = get_session
        self.get_current_user = get_current_user

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and log audit entry."""
        # Skip excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Skip static files
        if request.url.path.startswith("/static"):
            return await call_next(request)

        # Record start time
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Only log write operations (POST, PUT, PATCH, DELETE)
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return response

        # Get user info from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)
        username = getattr(request.state, "username", None)
        user_role = getattr(request.state, "user_role", None)
        client_ip = self._get_client_ip(request)

        # Determine action and resource
        action = self._determine_action(request)
        resource = self._determine_resource(request)

        # Log audit entry asynchronously (non-blocking)
        try:
            async with self.get_session() as session:
                audit_service = AuditService(session)
                await audit_service.log(
                    action=action,
                    resource=resource,
                    result=AuditResult.SUCCESS if response.status_code < 400 else AuditResult.FAILURE,
                    actor_user_id=UUID(user_id) if user_id else None,
                    actor_username=username,
                    actor_role=user_role,
                    actor_ip_address=client_ip,
                    context={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": int((time.time() - start_time) * 1000),
                    },
                )
                await session.commit()
        except Exception:
            # Don't fail the request if audit logging fails
            pass

        return response

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """Get client IP address from request."""
        # Check X-Forwarded-For header first (for proxied requests)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return None

    def _determine_action(self, request: Request) -> str:
        """Determine audit action from request."""
        method = request.method
        action = self.METHOD_ACTIONS.get(method, method.lower())

        # Special cases
        path = request.url.path
        if "restore" in path:
            action = "restore"
        elif "export" in path:
            action = "export"
        elif "execute" in path:
            action = "execute"

        return f"{action}"

    def _determine_resource(self, request: Request) -> str:
        """Determine resource from request path."""
        path = request.url.path

        # Remove API prefix and version
        if path.startswith("/api/v1/"):
            path = path[8:]

        # Extract resource name (first path segment)
        parts = path.strip("/").split("/")
        if parts:
            return parts[0]

        return "unknown"