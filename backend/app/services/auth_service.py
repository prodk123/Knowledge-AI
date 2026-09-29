"""Authentication and authorization services."""

import logging
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User, Role

logger = logging.getLogger(__name__)

# The name of the default least-privileged role assigned to all new self-registered users.
# This must match a role that exists (or will be created) in the database.
DEFAULT_USER_ROLE = "USER"


class UserAlreadyExistsError(Exception):
    """Raised when trying to register a user with an email that already exists."""
    pass


class AuthService:
    """Service for authentication and RBAC resolution."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_email(self, email: str) -> User | None:
        """Fetch a user by email, including roles and permissions."""
        stmt = (
            select(User)
            .where(User.email == email)
        )
        result = await self.db.scalars(stmt)
        return result.first()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Fetch a user by ID, including roles and permissions."""
        stmt = (
            select(User)
            .where(User.id == user_id)
        )
        result = await self.db.scalars(stmt)
        return result.first()

    async def authenticate_user(
        self, email: str, password: str, verify_password_fn
    ) -> User | None:
        """Authenticate user by email and password."""
        user = await self.get_user_by_email(email)
        if not user:
            return None
        if not verify_password_fn(password, user.password_hash):
            return None
        return user

    async def register_user(
        self,
        email: str,
        password: str,
        full_name: str,
        hash_password_fn,
    ) -> User:
        """
        Create a new user account.

        - Password is hashed server-side; the plaintext is never stored.
        - Role is assigned server-side as DEFAULT_USER_ROLE; the caller cannot elevate it.
        - Raises UserAlreadyExistsError if the email is taken.
        """
        # Check for duplicate email before attempting insert
        existing = await self.get_user_by_email(email)
        if existing:
            raise UserAlreadyExistsError(f"Email '{email}' is already registered.")

        # Fetch the default USER role. It MUST pre-exist (created via seed / migration).
        role_stmt = select(Role).where(Role.name == DEFAULT_USER_ROLE)
        role_result = await self.db.scalars(role_stmt)
        user_role = role_result.first()

        if user_role is None:
            # Safety fallback: create the role if it doesn't exist yet.
            # This should only happen in a fresh DB before seed data runs.
            logger.warning(
                "Default role '%s' not found — creating it automatically.", DEFAULT_USER_ROLE
            )
            user_role = Role(
                name=DEFAULT_USER_ROLE,
                description="Standard user with basic chat access",
            )
            self.db.add(user_role)
            await self.db.flush()  # Get the ID without committing

        password_hash = hash_password_fn(password)

        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            is_active=True,
        )
        user.roles.append(user_role)
        self.db.add(user)

        try:
            await self.db.commit()
            await self.db.refresh(user)
        except IntegrityError:
            await self.db.rollback()
            raise UserAlreadyExistsError(f"Email '{email}' is already registered.")

        logger.info("New user registered: %s (id=%s)", email, user.id)
        return user
