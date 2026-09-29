import argparse
import asyncio
import logging
import sys

from sqlalchemy import select

# Must be run with PYTHONPATH pointing to backend/
from app.db.database import async_session_factory, init_db
from app.models.auth import User, Role

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def assign_role(email: str, role_name: str, action: str):
    await init_db()
    async with async_session_factory() as session:
        # Fetch user
        stmt = select(User).where(User.email == email)
        user = (await session.scalars(stmt)).first()
        
        if not user:
            logger.error("User with email '%s' not found.", email)
            sys.exit(1)
            
        # Fetch role
        stmt = select(Role).where(Role.name == role_name)
        role = (await session.scalars(stmt)).first()
        
        if not role:
            logger.error("Role '%s' not found in database.", role_name)
            sys.exit(1)
            
        current_roles = {r.name for r in user.roles}
        
        if action == "add":
            if role_name in current_roles:
                logger.info("User '%s' already has role '%s'.", email, role_name)
            else:
                user.roles.append(role)
                await session.commit()
                logger.info("Successfully added role '%s' to user '%s'.", role_name, email)
        elif action == "remove":
            if role_name not in current_roles:
                logger.info("User '%s' does not have role '%s'.", email, role_name)
            else:
                user.roles = [r for r in user.roles if r.name != role_name]
                await session.commit()
                logger.info("Successfully removed role '%s' from user '%s'.", role_name, email)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage user roles out of band.")
    parser.add_argument("--email", required=True, help="User's email address")
    parser.add_argument("--role", required=True, help="Role name (e.g., 'admin', 'manager')")
    parser.add_argument("--action", choices=["add", "remove"], default="add", help="Action to perform")
    
    args = parser.parse_args()
    
    asyncio.run(assign_role(args.email, args.role, args.action))
