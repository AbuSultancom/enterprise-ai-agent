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
    {"id": 1, "name": "عبدالحميد", "name_en": "Abdulhameed", "role": "CEO / Owner",
     "department": "الإدارة", "phone": "966500000001", "email": "abdulhameed@company.sa"},
    {"id": 2, "name": "أحمد محمد", "name_en": "Ahmed Mohammed", "role": "محاسب",
     "department": "المالية", "phone": "966500000002", "email": "ahmed@company.sa"},
    {"id": 3, "name": "فاطمة علي", "name_en": "Fatima Ali", "role": "مديرة مبيعات",
     "department": "المبيعات", "phone": "966500000003", "email": "fatima@company.sa"},
    {"id": 4, "name": "خالد عبدالله", "name_en": "Khalid Abdullah", "role": "مدير مخازن",
     "department": "المخازن", "phone": "966500000004", "email": "khalid@company.sa"},
    {"id": 5, "name": "سارة عمر", "name_en": "Sara Omar", "role": "خدمة عملاء",
     "department": "الدعم", "phone": "966500000005", "email": "sara@company.sa"},
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
            lines = ["👥 دليل الموظفين / Employee Directory\n"]
            lines.append(f"إجمالي {len(employees)} موظف\n")
            for emp in employees:
                lines.append(
                    f"  🧑 {emp['name']} ({emp.get('name_en', '')}) — {emp.get('role', '')}\n"
                    f"     قسم: {emp.get('department', '')} | 📞 {emp.get('phone', '')} | ✉️ {emp.get('email', '')}\n"
                )
            return "".join(lines)

        q = query.lower()
        results = []
        for emp in employees:
            if (q in emp.get("name", "").lower() or
                q in emp.get("name_en", "").lower() or
                q in emp.get("department", "").lower() or
                q in emp.get("role", "").lower() or
                q in emp.get("phone", "") or
                q in emp.get("email", "").lower()):
                results.append(emp)

        if not results:
            return f"❌ لا يوجد موظف مطابق لـ \"{query}\"\n   No employee matches \"{query}\""

        lines = [f"🔍 نتائج البحث عن \"{query}\" — {len(results)} موظف\n"]
        for emp in results:
            lines.append(
                f"  🧑 {emp['name']} ({emp.get('name_en', '')})\n"
                f"     الدور: {emp.get('role', '')} | القسم: {emp.get('department', '')}\n"
                f"     📞 {emp.get('phone', '')} | ✉️ {emp.get('email', '')}\n"
            )
        return "".join(lines)

    except Exception as e:
        return f"❌ خطأ في البحث: {e}"


async def add_employee(name: str, role: str = "", department: str = "",
                        phone: str = "", email: str = "", name_en: str = "") -> str:
    """Add a new employee to the directory.

    Args:
        name: Full name (Arabic or English)
        role: Job title/role
        department: Department name
        phone: Phone number
        email: Email address
        name_en: English version of the name (optional)

    Returns:
        Confirmation message.
    """
    try:
        employees = get_employees()
        new_id = max((e.get("id", 0) for e in employees), default=0) + 1
        emp = {
            "id": new_id,
            "name": name,
            "name_en": name_en or name,
            "role": role,
            "department": department,
            "phone": phone,
            "email": email,
        }
        employees.append(emp)
        with open(EMPLOYEES_FILE, "w", encoding="utf-8") as f:
            json.dump(employees, f, ensure_ascii=False, indent=2)
        return f"✅ تمت إضافة الموظف: {name}\n   ID: {new_id}\n   الدور: {role}\n   القسم: {department}"
    except Exception as e:
        return f"❌ خطأ في الإضافة: {e}"
