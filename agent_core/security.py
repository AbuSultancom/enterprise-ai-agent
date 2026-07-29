"""Role-Based Access Control (RBAC) and Security Management for Enterprise AI Agent."""
from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Set


class Role(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


@dataclass
class UserContext:
    user_id: str
    username: str
    role: Role = Role.EMPLOYEE
    department: str = "General"
    permissions: Set[str] = field(default_factory=set)


# Restrict sensitive tools by default to specific roles
RESTRICTED_TOOLS: dict[str, Set[Role]] = {
    # Accounting & ERP tools restricted to Managers & Admins
    "get_sales_summary": {Role.ADMIN, Role.MANAGER},
    "get_revenue_by_month": {Role.ADMIN, Role.MANAGER},
    "get_expenses_summary": {Role.ADMIN, Role.MANAGER},
    "get_vendor_balances": {Role.ADMIN, Role.MANAGER},
    "add_database": {Role.ADMIN},
    "diagnose_connection": {Role.ADMIN},
    "show_schema_config": {Role.ADMIN},
}


class SecurityManager:
    """Enforces access control rules for users and tools."""

    @staticmethod
    def is_tool_allowed(tool_name: str, user: UserContext | None) -> tuple[bool, str]:
        """Check if user has permission to invoke tool_name."""
        if user is None:
            # Default unauthenticated user behaves as EMPLOYEE
            user = UserContext(user_id="guest", username="guest", role=Role.EMPLOYEE)

        if user.role == Role.ADMIN:
            return True, "Allowed (Admin)"

        allowed_roles = RESTRICTED_TOOLS.get(tool_name)
        if allowed_roles is None:
            # Tool has no restriction
            return True, "Allowed"

        if user.role in allowed_roles:
            return True, f"Allowed ({user.role.value})"

        return False, f"Access denied: tool '{tool_name}' requires role {[r.value for r in allowed_roles]}"
