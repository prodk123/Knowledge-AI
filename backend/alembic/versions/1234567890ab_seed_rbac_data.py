"""seed_rbac_data

Revision ID: 1234567890ab
Revises: faf98997009a
Create Date: 2026-09-07 15:00:00.000000

"""
from typing import Sequence, Union
import uuid
import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '1234567890ab'
down_revision: Union[str, Sequence[str], None] = '5a5a04ebd884'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Idempotently seed roles and permissions."""
    conn = op.get_bind()

    # Define the precise list of required permissions
    permissions = {
        "chat.use": "Use chat and agent functionality",
        "documents.read": "Read and list documents",
        "documents.upload": "Upload new documents",
        "documents.delete": "Delete documents",
        "documents.manage": "Manage document RBAC scopes",
        "users.read": "View the user list",
        "users.manage": "Manage user roles and activation",
        "evaluation.view": "View system evaluations",
    }

    # Define exact permissions for ADMIN explicitly (do not just grant all dynamic permissions)
    admin_perms = [
        "chat.use",
        "documents.read",
        "documents.upload",
        "documents.delete",
        "documents.manage",
        "users.read",
        "users.manage",
        "evaluation.view"
    ]

    # Define exact permissions for USER
    user_perms = [
        "chat.use"
    ]

    # Insert missing permissions idempotently
    for p_name, p_desc in permissions.items():
        conn.execute(
            sa.text(
                "INSERT INTO permissions (id, name, description, created_at) "
                "VALUES (:id, :name, :desc, :created_at) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {
                "id": str(uuid.uuid4()),
                "name": p_name,
                "desc": p_desc,
                "created_at": datetime.datetime.now(datetime.timezone.utc)
            }
        )

    # Insert standard roles idempotently
    roles = ["USER", "employee", "hr", "finance", "marketing", "manager", "c_level", "admin"]
    for role_name in roles:
        conn.execute(
            sa.text(
                "INSERT INTO roles (id, name, description, created_at) "
                "VALUES (:id, :name, :desc, :created_at) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {
                "id": str(uuid.uuid4()),
                "name": role_name,
                "desc": f"{role_name} role",
                "created_at": datetime.datetime.now(datetime.timezone.utc)
            }
        )

    # Helper function to map a role to a set of permissions
    def assign_permissions(role_name: str, perm_names: list[str]):
        # Get role ID
        role_res = conn.execute(sa.text("SELECT id FROM roles WHERE name = :name"), {"name": role_name}).first()
        if not role_res:
            return
        role_id = role_res[0]

        for p_name in perm_names:
            p_res = conn.execute(sa.text("SELECT id FROM permissions WHERE name = :name"), {"name": p_name}).first()
            if not p_res:
                continue
            perm_id = p_res[0]

            # Insert Association
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "VALUES (:role_id, :perm_id) "
                    "ON CONFLICT (role_id, permission_id) DO NOTHING"
                ),
                {
                    "role_id": role_id,
                    "perm_id": perm_id
                }
            )

    # Explicitly map permissions
    assign_permissions("USER", user_perms)
    assign_permissions("admin", admin_perms)

    # Other roles (manager, c_level, etc.) can be left alone or seeded as needed.
    # The requirement strictly asked for explicit ADMIN and USER.
    assign_permissions("employee", ["chat.use", "documents.read"])
    assign_permissions("hr", ["chat.use", "documents.read"])
    assign_permissions("finance", ["chat.use", "documents.read"])
    assign_permissions("marketing", ["chat.use", "documents.read"])
    assign_permissions("manager", ["chat.use", "documents.read", "documents.upload"])
    assign_permissions("c_level", ["chat.use", "documents.read", "documents.upload", "documents.manage"])


def downgrade() -> None:
    pass
