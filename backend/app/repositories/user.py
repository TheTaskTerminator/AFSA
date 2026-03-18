"""User repository."""
from typing import List, Optional
from uuid import UUID

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository
from app.schemas.user import UserCreate, UserUpdate


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    """User repository for database operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def create(self, obj_in: UserCreate) -> User:
        """Create a new user with hashed password."""
        user_data = obj_in.model_dump()
        # Hash the password and rename to password_hash
        plain_password = user_data.pop("password")
        user_data["password_hash"] = hash_password(plain_password)

        db_obj = self.model(**user_data)
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_role(self, role: str, skip: int = 0, limit: int = 100) -> List[User]:
        """Get users by role."""
        result = await self.session.execute(
            select(User).where(User.role == role).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_active_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all active users."""
        result = await self.session.execute(
            select(User).where(User.is_active == True).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def update_password(self, user_id: UUID, password_hash: str) -> Optional[User]:
        """Update user password."""
        user = await self.get(user_id)
        if user is None:
            return None
        user.password_hash = password_hash
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def deactivate(self, user_id: UUID) -> Optional[User]:
        """Deactivate a user."""
        user = await self.get(user_id)
        if user is None:
            return None
        user.is_active = False
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def activate(self, user_id: UUID) -> Optional[User]:
        """Activate a user."""
        user = await self.get(user_id)
        if user is None:
            return None
        user.is_active = True
        await self.session.flush()
        await self.session.refresh(user)
        return user