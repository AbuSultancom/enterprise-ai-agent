"""
Employee Directory Tool
=======================
Agent knows your employees: search by name, department, role, contact info.
"""

import json
import os
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMPLOYEES_FILE = os.path.join(ROOT, "config", "employees.json")

DEFAULT_EMPLOYEES = [
    {"id": 1, "name": "Abdulhameed", "role": "CEO / Owner",
     "department": "Administration", "phone": "966500000001", "email": "abdulhameed@company.sa"},
    {"id": 2, "name": "Ahmed Mohammed", "role": "Accountant",
     "department": "Finance", "phone": "966500000002", "email": "ahmed@company.sa"},
    {"id": 3, "name": "Fatima Ali", "role": "Sales Manager",
     "department": "Sales", "phone": "966500000003", "email": "fatima@company.sa"},
    {"id": 4, "name": "Khalid Abdullah", "role": "Warehouse Manager",
     "department": "Warehouse", "phone": "966500000004", "email": "khalid@company.sa"},
    {"id": 5, "name": "Sara Omar", "role": "Customer Support",
     "department": "Support", "phone": "966500000005", "email": "sara@company.sa"},
]


def get_employees() -> list[dict]:
    """Load employees from config file, create default if missing."""
    os.makedirs(os.path.dirname(EMPLOYEES_FILE), exist_ok=True)
    if not os.path.exists(EMPLOYEES_FILE):
        with open(EMPLOYEES_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_EMPLOYEES, f, ensure_ascii=False, indent=2)
        return DEFAULT_EMPLOYEES
    try:
        with open(EMPLOYEES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return DEFAULT_EMPLOYEES


async def search_employee(query: str = "") -> str:
    """Search employees by name, department, role, or phone.

    Args:
        query: Search term (name, department, role, or phone number)
               Leave empty to list all employees.

    Returns:
        Formatted list of matching employees.
    """
    try:
        employees = get_employees()
        if not query.strip():
            # List all
            lines = ["👥 Employee Directory\n"]
            lines.append(f"Total {len(employees)} employee(s)\n")
            for emp in employees:
                lines.append(
                    f"  🧑 {emp['name']} — {emp.get('role', '')}\n"
                    f"     Department: {emp.get('department', '')} | 📞 {emp.get('phone', '')} | ✉️ {emp.get('email', '')}\n"
                )
            return "".join(lines)

        q = query.lower()
        results = []
        for emp in employees:
            if (q in emp.get("name", "").lower() or
                q in emp.get("department", "").lower() or
                q in emp.get("role", "").lower() or
                q in emp.get("phone", "") or
                q in emp.get("email", "").lower()):
                results.append(emp)

        if not results:
            return f"❌ No employee matches \"{query}\""

        lines = [f"🔍 Search results for \"{query}\" — {len(results)} employee(s)\n"]
        for emp in results:
            lines.append(
                f"  🧑 {emp['name']}\n"
                f"     Role: {emp.get('role', '')} | Department: {emp.get('department', '')}\n"
                f"     📞 {emp.get('phone', '')} | ✉️ {emp.get('email', '')}\n"
            )
        return "".join(lines)

    except Exception as e:
        return f"❌ Search error: {e}"


async def add_employee(name: str, role: str = "", department: str = "",
                        phone: str = "", email: str = "") -> str:
    """Add a new employee to the directory.

    Args:
        name: Full name (Arabic or English)
        role: Job title/role
        department: Department name
        phone: Phone number
        email: Email address

    Returns:
        Confirmation message.
    """
    try:
        employees = get_employees()
        new_id = max((e.get("id", 0) for e in employees), default=0) + 1
        emp = {
            "id": new_id,
            "name": name,
            "role": role,
            "department": department,
            "phone": phone,
            "email": email,
        }
        employees.append(emp)
        with open(EMPLOYEES_FILE, "w", encoding="utf-8") as f:
            json.dump(employees, f, ensure_ascii=False, indent=2)
        return f"✅ Employee added: {name}\n   ID: {new_id}\n   Role: {role}\n   Department: {department}"
    except Exception as e:
        return f"❌ Addition error: {e}"
