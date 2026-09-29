import asyncio
import uuid
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.database import async_session_factory, init_db
from app.core.security import get_password_hash
from app.models.auth import User, Role, Permission
from app.models.document import DocumentRecord, DocumentStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_data():
    await init_db()
    
    async with async_session_factory() as session:
        # Create Permissions
        perms = ["documents.read", "documents.upload", "documents.delete", "documents.manage", "users.read", "users.manage", "chat.use", "evaluation.view"]
        db_perms = {}
        for p in perms:
            stmt = select(Permission).where(Permission.name == p)
            result = await session.scalars(stmt)
            perm = result.first()
            if not perm:
                perm = Permission(name=p, description=f"Permission for {p}")
                session.add(perm)
            db_perms[p] = perm
            
        await session.commit()
        
        # Define Roles
        roles_data = {
            "USER": ["chat.use"],
            "employee": ["chat.use", "documents.read"],
            "hr": ["chat.use", "documents.read"],
            "finance": ["chat.use", "documents.read"],
            "marketing": ["chat.use", "documents.read"],
            "manager": ["chat.use", "documents.read", "documents.upload"],
            "c_level": ["chat.use", "documents.read", "documents.upload", "documents.manage"],
            "admin": perms
        }
        
        db_roles = {}
        for role_name, role_perms in roles_data.items():
            stmt = select(Role).where(Role.name == role_name)
            result = await session.scalars(stmt)
            role = result.first()
            if not role:
                role = Role(name=role_name, description=f"{role_name} role")
                session.add(role)
            # update permissions
            role.permissions = [db_perms[p] for p in role_perms]
            db_roles[role_name] = role
            
        await session.commit()
        
        # Define Users
        users_data = [
            ("employee@example.com", "Employee User", ["employee"]),
            ("hr@example.com", "HR User", ["hr"]),
            ("finance@example.com", "Finance User", ["finance"]),
            ("marketing@example.com", "Marketing User", ["marketing"]),
            ("manager@example.com", "Manager User", ["manager"]),
            ("executive@example.com", "Executive User", ["c_level"]),
            ("admin@example.com", "Admin User", ["admin"]),
        ]
        
        hashed_password = get_password_hash("password123")
        
        for email, full_name, user_roles in users_data:
            stmt = select(User).where(User.email == email)
            result = await session.scalars(stmt)
            user = result.first()
            if not user:
                user = User(
                    email=email,
                    full_name=full_name,
                    password_hash=hashed_password,
                    is_active=True
                )
                session.add(user)
            # update roles
            user.roles = [db_roles[r] for r in user_roles]
            
        await session.commit()
        logger.info("Users, roles, and permissions seeded successfully.")
        
        # Sample document access policies
        docs = {
            "employee_handbook.pdf": ["employee", "hr", "manager", "c_level", "admin"],
            "finance_policy.pdf": ["finance", "manager", "c_level", "admin"],
            "marketing_policy.pdf": ["marketing", "manager", "c_level", "admin"],
            "executive_strategy.pdf": ["c_level", "admin"]
        }
        
        for filename, allowed in docs.items():
            # Let's create dummy documents if they don't exist just so we can test the UI list logic
            stmt = select(DocumentRecord).where(DocumentRecord.original_filename == filename)
            result = await session.scalars(stmt)
            doc = result.first()
            if not doc:
                doc = DocumentRecord(
                    id=uuid.uuid4(),
                    filename=f"{uuid.uuid4()}_{filename}",
                    original_filename=filename,
                    file_type="application/pdf",
                    file_size=1024,
                    storage_path=f"/fake/path/{filename}",
                    status=DocumentStatus.PROCESSED.value,
                    allowed_roles=allowed
                )
                session.add(doc)
            else:
                doc.allowed_roles = allowed
                
        await session.commit()
        logger.info("Sample documents seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed_data())
