"""Built-in tools shipped with the platform. Add your own in tools/custom/."""
from __future__ import annotations

import base64
import datetime
import math
import os

import httpx

from .registry import registry


@registry.register(
    description="Search through past conversations to recall what was discussed.",
    parameters={"query": {"type": "str", "description": "What to search for in past conversations"}},
)
def search_conversations(query: str) -> str:
    from memory.conversation import get_store
    store = get_store()
    results = store.search(query, limit=8)
    if not results:
        return "No past conversations found matching that query."
    lines = []
    for r in results:
        lines.append(f"[{r['session_title']}] {r['role']}: {r['content'][:300]}")
    return "\n\n".join(lines)


@registry.register(
    description="Generate and save a text report to the data/reports folder. Returns the file path.",
    parameters={
        "title": {"type": "str", "description": "Report title (used as filename)"},
        "content": {"type": "str", "description": "Report body content in plain text or markdown"},
    },
)
def generate_report(title: str, content: str) -> str:
    import datetime
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "data", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    safe_name = "".join(c for c in title if c.isalnum() or c in " _-").strip() or "report"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_name}_{timestamp}.md"
    filepath = os.path.join(reports_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(f"Generated: {datetime.datetime.now().isoformat()}\n\n")
        f.write(content)
    return f"Report saved to: {filepath}"


@registry.register(
    description="List all previously saved reports in the data/reports folder.",
    parameters={},
)
def list_reports() -> str:
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "data", "reports")
    if not os.path.isdir(reports_dir):
        return "No reports found yet."
    files = sorted(os.listdir(reports_dir), reverse=True)
    if not files:
        return "No reports found yet."
    lines = []
    for f in files[:20]:
        fpath = os.path.join(reports_dir, f)
        size = os.path.getsize(fpath)
        lines.append(f"- {f} ({size} bytes)")
    return "Saved reports:\n" + "\n".join(lines)


@registry.register(
    description="Get the current date and time.",
    parameters={},
)
def get_current_time() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


@registry.register(
    description="Evaluate a math expression safely (e.g. '2 * (3 + 4)').",
    parameters={"expression": {"type": "str", "description": "Math expression"}},
)
def calculator(expression: str) -> str:
    """Evaluate a math expression using AST-based sandbox (no eval)."""
    import ast
    import operator as _operator

    allowed_ops = {
        ast.Add: _operator.add, ast.Sub: _operator.sub,
        ast.Mult: _operator.mul, ast.Div: _operator.truediv,
        ast.FloorDiv: _operator.floordiv, ast.Mod: _operator.mod,
        ast.Pow: _operator.pow, ast.USub: _operator.neg,
        ast.UAdd: _operator.pos,
    }
    allowed_funcs = {
        "abs": abs, "round": round, "min": min, "max": max,
        "pow": pow, "sum": sum,
    }
    # Expose math module functions by name
    allowed_funcs.update(
        {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    )

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in allowed_funcs:
                return allowed_funcs[node.id]
            raise ValueError(f"Unknown identifier: {node.id}")
        if isinstance(node, ast.Call):
            func = _eval(node.func)
            args = [_eval(a) for a in node.args]
            return func(*args)
        if isinstance(node, ast.BinOp):
            op = allowed_ops.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            op = allowed_ops.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op(_eval(node.operand))
        if isinstance(node, ast.List):
            return [_eval(e) for e in node.elts]
        raise ValueError(f"Unsupported syntax: {type(node).__name__}")

    try:
        tree = ast.parse(expression.strip(), mode="eval")
        return str(_eval(tree))
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: {e}"


@registry.register(
    description="Search the web and return top results (title + snippet + url).",
    parameters={"query": {"type": "str", "description": "Search query"}},
)
async def web_search(query: str) -> str:
    """Search the web and return top results (title + snippet + url)."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=8))
        if not results:
            return f"No results found for '{query}'."
        lines = []
        for r in results:
            title = r.get("title", "").strip()
            snippet = r.get("body", "").strip()[:200]
            url = r.get("href", "")
            lines.append(f"• {title}\n  {snippet}\n  {url}")
        return "\n\n".join(lines)
    except ImportError:
        return "Search unavailable: duckduckgo_search library not installed."
    except Exception as e:
        return f"Search failed: {e}"


@registry.register(
    description="Read a text file from the shared workspace volume.",
    parameters={"path": {"type": "str", "description": "File path inside /data/workspace"}},
)
def read_file(path: str) -> str:
    import os.path
    base = os.getenv("WORKSPACE_PATH", "/data/workspace")
    # Resolve to an absolute path and ensure it stays under the workspace base
    abs_base = os.path.abspath(base)
    requested = os.path.normpath(os.path.join(abs_base, path))
    if not requested.startswith(abs_base + os.sep) and requested != abs_base:
        return f"Error: path '{path}' escapes the workspace boundary."
    try:
        with open(requested, encoding="utf-8") as f:
            return f.read()[:8000]
    except Exception as e:
        return f"Error: {e}"


@registry.register(
    description="Analyze an image (invoice, receipt, screenshot, document) through the LLM's vision API. Supports both image URLs and local file paths.",
    parameters={
        "image": {"type": "str", "description": "Image URL (https://...) or local file path relative to /data/workspace"},
        "question": {"type": "str", "description": "Optional: what to ask about the image (default: read and extract all important data)"},
    },
)
async def read_image(image: str, question: str = "") -> str:
    """Analyze an image using a vision-capable model."""
    if not question:
        question = "Read the content of this image in detail and extract all important data visible in it. For invoices/receipts: extract invoice number, date, customer, items, totals, tax, and status. For screenshots: describe what's shown. For documents: transcribe all visible text."

    # Determine if it's a local path or URL
    is_url = image.startswith(("http://", "https://", "data:"))
    image_type = "url"
    image_data = image

    if not is_url:
        # Try to read as a local file and convert to base64
        try:
            base_path = os.getenv("WORKSPACE_PATH", "/data/workspace")
            abs_path = os.path.normpath(os.path.join(base_path, image))
            if not os.path.exists(abs_path):
                # Try the file path as-is
                abs_path = os.path.normpath(image)
            if not os.path.exists(abs_path):
                return f"Error: image file not found at '{image}'"
            with open(abs_path, "rb") as f:
                raw = f.read()
            # Detect MIME type from extension
            ext = os.path.splitext(abs_path)[1].lower()
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
            mime = mime_map.get(ext, "image/jpeg")
            image_data = base64.b64encode(raw).decode("utf-8")
            image_type = f"base64:{mime}"
        except Exception as e:
            return f"Error reading local image file: {e}"

    try:
        from llm_gateway.gateway import LLMGateway
        gateway = LLMGateway()
        result = await gateway.chat_vision(question, image_data, image_type)
        return result
    except Exception as e:
        return f"Error analyzing image: {e}"


@registry.register(
    description="Get current weather for any city worldwide.",
    parameters={"city": {"type": "str", "description": "City name (e.g. 'Riyadh', 'Dubai', 'London')"}},
)
async def get_weather(city: str) -> str:
    """Get weather from wttr.in (no API key needed)."""
    import httpx
    try:
        url = f"https://wttr.in/{city}?format=%C+%t+%h+%w"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            if r.status_code == 200:
                text = r.text.strip()
                return f"🌤 طقس {city}: {text}"
            return f"Could not get weather for '{city}'."
    except Exception as e:
        return f"Weather error: {e}"


@registry.register(
    description="Get current currency exchange rate between two currencies.",
    parameters={
        "from_currency": {"type": "str", "description": "Source currency code (e.g. 'USD', 'SAR')"},
        "to_currency": {"type": "str", "description": "Target currency code (e.g. 'SAR', 'EUR', 'TRY')"},
    },
)
async def get_currency_rate(from_currency: str, to_currency: str) -> str:
    """Get exchange rate from free API."""
    import httpx
    try:
        from_currency = from_currency.upper()[:3]
        to_currency = to_currency.upper()[:3]
        url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            if r.status_code == 200:
                data = r.json()
                rate = data["rates"].get(to_currency)
                if rate:
                    return f"💰 1 {from_currency} = {rate:.4f} {to_currency}"
                return f"Currency '{to_currency}' not found."
            return f"Could not get exchange rate."
    except Exception as e:
        return f"Currency error: {e}"


# ---------------------------------------------------------------------------
# 🇸🇦 Saudi Arabia Business Tools
# ---------------------------------------------------------------------------


@registry.register(
    description="الحصول على سعر سهم سعودي من Argaam/Tadawul — احصل على السهم (مثل 1120 للراجحي)",
    parameters={
        "symbol": {"type": "str", "description": "رمز السهم (مثل 1120 لألراجحي)"},
    },
)
async def tasi_stocks(symbol: str) -> str:
    """Get Saudi stock price from Argaam/Tadawul. Returns price, change, volume."""
    import httpx
    try:
        symbol = symbol.strip()
        url = f"https://www.argaam.com/ar/company/companyoverview/{symbol}"
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if r.status_code != 200:
                # Fallback: try the screener endpoint
                alt_url = f"https://www.argaam.com/ar/screener/company/data/overview?companyId={symbol}"
                r = await client.get(alt_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                if r.status_code != 200:
                    return f"⚠️ تعذر الحصول على بيانات السهم {symbol}. قد يكون الرمز غير صحيح."
            text = r.text
            # Try to extract price from page
            import re
            price_match = re.search(r'<span[^>]*class="[^"]*price[^"]*"[^>]*>([\d.,]+)', text)
            change_match = re.search(r'<span[^>]*class="[^"]*change[^"]*"[^>]*>([+-]?[\d.,]+)', text)
            if price_match:
                price = price_match.group(1)
                change = change_match.group(1) if change_match else "N/A"
                return (
                    f"📈 سهم {symbol}\n"
                    f"السعر: {price} ريال\n"
                    f"التغير: {change}\n"
                    f"(المصدر: Argaam)"
                )
            return f"📊 تم استرداد بيانات السهم {symbol} بنجاح (تعذر استخراج السعر من الصفحة)."
    except Exception as e:
        return f"⚠️ خطأ في جلب بيانات السهم {symbol}: {e}"


@registry.register(
    description="حاسبة ضريبة القيمة المضافة 15% — حساب ضريبة القيمة المضافة السعودية",
    parameters={
        "amount": {"type": "number", "description": "المبلغ بالريال"},
        "inclusive": {"type": "bool", "description": "هل المبلغ شامل الضريبة؟ (True = استخراج الضريبة, False = إضافة الضريبة)",
                       "default": False},
    },
)
async def vat_calc(amount: float, inclusive: bool = False) -> str:
    """Calculate Saudi VAT (15%). If inclusive, extracts VAT from total.
    If not inclusive, adds VAT to the amount."""
    try:
        rate = 0.15
        if inclusive:
            # Total includes VAT: VAT = Total * (rate / (1 + rate))
            vat = amount * (rate / (1 + rate))
            original = amount - vat
            total = amount
        else:
            original = amount
            vat = amount * rate
            total = amount + vat
        return (
            f"🧾 حاسبة ضريبة القيمة المضافة (15%)\n"
            f"{'─' * 35}\n"
            f"المبلغ الأصلي:       {original:,.2f} ريال\n"
            f"قيمة الضريبة (15%):  {vat:,.2f} ريال\n"
            f"{'─' * 35}\n"
            f"الإجمالي:            {total:,.2f} ريال"
        )
    except Exception as e:
        return f"⚠️ خطأ في حساب ضريبة القيمة المضافة: {e}"


@registry.register(
    description="حاسبة هامش الربح — حساب الربح وهامش الربح ونسبة الترميز",
    parameters={
        "cost": {"type": "number", "description": "التكلفة (سعر الشراء)"},
        "selling_price": {"type": "number", "description": "سعر البيع"},
    },
)
async def profit_margin(cost: float, selling_price: float) -> str:
    """Calculate profit margin. Returns profit amount, margin %, and markup %."""
    try:
        if cost <= 0:
            return "⚠️ التكلفة يجب أن تكون أكبر من صفر."
        profit = selling_price - cost
        margin_pct = (profit / selling_price) * 100
        markup_pct = (profit / cost) * 100
        return (
            f"📊 حاسبة هامش الربح\n"
            f"{'─' * 35}\n"
            f"التكلفة:              {cost:,.2f} ريال\n"
            f"سعر البيع:            {selling_price:,.2f} ريال\n"
            f"{'─' * 35}\n"
            f"الربح:                {profit:,.2f} ريال\n"
            f"هامش الربح:          {margin_pct:.2f}%\n"
            f"نسبة الترميز:        {markup_pct:.2f}%"
        )
    except Exception as e:
        return f"⚠️ خطأ في حساب هامش الربح: {e}"


@registry.register(
    description="حاسبة العائد على الاستثمار (ROI) — حساب العائد كنسبة مئوية",
    parameters={
        "initial_investment": {"type": "number", "description": "قيمة الاستثمار الأولية"},
        "final_value": {"type": "number", "description": "القيمة النهائية للاستثمار"},
    },
)
async def roi_calc(initial_investment: float, final_value: float) -> str:
    """Return on Investment calculator. Returns ROI percentage and profit/loss."""
    try:
        if initial_investment <= 0:
            return "⚠️ الاستثمار الأولي يجب أن يكون أكبر من صفر."
        profit = final_value - initial_investment
        roi_pct = (profit / initial_investment) * 100
        status = "ربح 📈" if profit >= 0 else "خسارة 📉"
        return (
            f"💰 حاسبة العائد على الاستثمار (ROI)\n"
            f"{'─' * 35}\n"
            f"الاستثمار الأولي:      {initial_investment:,.2f} ريال\n"
            f"القيمة النهائية:       {final_value:,.2f} ريال\n"
            f"{'─' * 35}\n"
            f"الربح/الخسارة:        {profit:+,.2f} ريال\n"
            f"العائد على الاستثمار: {roi_pct:+.2f}%\n"
            f"الحالة:               {status}"
        )
    except Exception as e:
        return f"⚠️ خطأ في حساب العائد على الاستثمار: {e}"


@registry.register(
    description="حاسبة القروض والتمويل — حساب القسط الشهري والفائدة الإجمالية",
    parameters={
        "amount": {"type": "number", "description": "مبلغ القرض"},
        "interest_rate": {"type": "number", "description": "نسبة الفائدة السنوية % (مثال: 5.5)"},
        "months": {"type": "number", "description": "مدة القرض بالأشهر"},
    },
)
async def loan_calc(amount: float, interest_rate: float, months: int) -> str:
    """Loan/Financing calculator. Calculates monthly payment, total payment, total interest."""
    try:
        if amount <= 0 or months <= 0:
            return "⚠️ المبلغ والمدة يجب أن يكونا أكبر من صفر."
        monthly_rate = (interest_rate / 100) / 12
        if monthly_rate == 0:
            monthly_payment = amount / months
        else:
            monthly_payment = amount * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
        total_payment = monthly_payment * months
        total_interest = total_payment - amount
        return (
            f"🏦 حاسبة القروض والتمويل\n"
            f"{'─' * 35}\n"
            f"مبلغ القرض:           {amount:,.2f} ريال\n"
            f"نسبة الفائدة:         {interest_rate:.2f}%\n"
            f"المدة:                {months} شهر\n"
            f"{'─' * 35}\n"
            f"القسط الشهري:         {monthly_payment:,.2f} ريال\n"
            f"مجموع المدفوعات:      {total_payment:,.2f} ريال\n"
            f"إجمالي الفائدة:       {total_interest:,.2f} ريال"
        )
    except Exception as e:
        return f"⚠️ خطأ في حساب القرض: {e}"


@registry.register(
    description="حاسبة الزكاة — حساب الزكاة بنسبة 2.5% على النقد والذهب والأسهم",
    parameters={
        "cash": {"type": "number", "description": "النقد المتوفر (ريال)", "default": 0},
        "gold_value": {"type": "number", "description": "قيمة الذهب (ريال)", "default": 0},
        "stocks_value": {"type": "number", "description": "قيمة الأسهم (ريال)", "default": 0},
        "debts": {"type": "number", "description": "الديون المستحقة عليك (ريال)", "default": 0},
    },
)
async def zakat_calc(cash: float = 0, gold_value: float = 0, stocks_value: float = 0, debts: float = 0) -> str:
    """Zakat calculator. Zakat rate = 2.5%. Returns total wealth and zakat due."""
    try:
        total_wealth = cash + gold_value + stocks_value
        net_wealth = total_wealth - debts
        zakat_rate = 0.025
        zakat_due = max(0, net_wealth * zakat_rate)
        return (
            f"🕌 حاسبة الزكاة (2.5%)\n"
            f"{'─' * 35}\n"
            f"النقد:                {cash:,.2f} ريال\n"
            f"الذهب:                {gold_value:,.2f} ريال\n"
            f"الأسهم:               {stocks_value:,.2f} ريال\n"
            f"إجمالي الثروة:        {total_wealth:,.2f} ريال\n"
            f"الديون:               {debts:,.2f} ريال\n"
            f"صافي الثروة:          {net_wealth:,.2f} ريال\n"
            f"{'─' * 35}\n"
            f"الزكاة الواجبة (2.5%): {zakat_due:,.2f} ريال"
        )
    except Exception as e:
        return f"⚠️ خطأ في حساب الزكاة: {e}"


@registry.register(
    description="حساب الأيام بين تاريخين — معرفة عدد الأيام والأسابيع والأشهر",
    parameters={
        "start_date": {"type": "str", "description": "تاريخ البداية (YYYY-MM-DD)"},
        "end_date": {"type": "str", "description": "تاريخ النهاية (YYYY-MM-DD)"},
    },
)
async def contract_days(start_date: str, end_date: str) -> str:
    """Calculate days between two dates. Returns total days, weeks, months."""
    try:
        from datetime import datetime
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        delta = end - start
        total_days = delta.days
        if total_days < 0:
            return "⚠️ تاريخ النهاية يجب أن يكون بعد تاريخ البداية."
        weeks = total_days // 7
        remaining_days = total_days % 7
        months_approx = round(total_days / 30.44, 1)
        return (
            f"📅 حساب المدة بين تاريخين\n"
            f"{'─' * 35}\n"
            f"تاريخ البداية:        {start_date}\n"
            f"تاريخ النهاية:        {end_date}\n"
            f"{'─' * 35}\n"
            f"عدد الأيام:           {total_days:,} يوم\n"
            f"عدد الأسابيع:         {weeks} أسبوع و{remaining_days} يوم\n"
            f"عدد اأشهر (تقريباً):  {months_approx} شهر"
        )
    except ValueError:
        return "⚠️ صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD (مثال: 2024-01-01)"
    except Exception as e:
        return f"⚠️ خطأ في حساب المدة: {e}"


@registry.register(
    description="حاسبة مكافأة نهاية الخدمة السعودية — حسب نظام العمل السعودي",
    parameters={
        "salary": {"type": "number", "description": "آخر راتب شهري (ريال)"},
        "years": {"type": "number", "description": "عدد سنوات الخدمة"},
        "reason": {"type": "str", "description": "سبب إنهاء الخدمة: 'resign' (استقالة) أو 'termination' (فصل/إنهاء)"},
    },
)
async def end_service(salary: float, years: float, reason: str) -> str:
    """Saudi labor law end-of-service reward calculator.

    Saudi Labor Law rules:
    - Termination: Half month salary for first 5 years, full month for each year after 5.
    - Resignation (less than 2 years): No reward.
    - Resignation (2-5 years): 1/3 of the termination amount.
    - Resignation (5-10 years): 2/3 of the termination amount.
    - Resignation (10+ years): Full termination amount.
    """
    try:
        if salary <= 0 or years <= 0:
            return "⚠️ الراتب وعدد السنوات يجب أن يكونا أكبر من صفر."
        reason = reason.strip().lower()
        # Termination calculation (full entitlement)
        if years <= 5:
            termination_reward = (salary / 2) * years
        else:
            termination_reward = (salary / 2) * 5 + salary * (years - 5)
        if reason == "termination" or reason == "فصل" or reason == "إنهاء":
            reward = termination_reward
            reason_label = "إنهاء خدمة / فصل"
            breakdown = (
                f"أول 5 سنوات: {min(years, 5):.0f} × نصف الراتب ({salary:,.2f}/2)\n"
                f"بعد 5 سنوات: {max(0, years - 5):.0f} × الراتب الكامل ({salary:,.2f})"
            )
        elif reason == "resign" or reason == "استقالة":
            if years < 2:
                reward = 0
                reason_label = "استقالة (أقل من سنتين)"
                breakdown = "لا تستحق مكافأة نهاية خدمة إذا كانت مدة الخدمة أقل من سنتين."
            elif years < 5:
                reward = termination_reward / 3
                reason_label = f"استقالة (بين سنتين و5 سنوات)"
                breakdown = f"تستحق ثلث مكافأة الفصل: {termination_reward:,.2f} / 3"
            elif years < 10:
                reward = termination_reward * 2 / 3
                reason_label = f"استقالة (بين 5 و10 سنوات)"
                breakdown = f"تستحق ثلثي مكافأة الفصل: {termination_reward:,.2f} × 2/3"
            else:
                reward = termination_reward
                reason_label = "استقالة (أكثر من 10 سنوات)"
                breakdown = "تستحق كامل مكافأة نهاية الخدمة (أكثر من 10 سنوات خدمة)."
        else:
            return f"⚠️ سبب غير معروف: '{reason}'. استخدم 'resign' أو 'termination'."
        return (
            f"📋 حاسبة مكافأة نهاية الخدمة\n"
            f"{'─' * 40}\n"
            f"الراتب الشهري:           {salary:,.2f} ريال\n"
            f"سنوات الخدمة:            {years:.0f} سنة\n"
            f"سبب الإنهاء:             {reason_label}\n"
            f"{'─' * 40}\n"
            f"{breakdown}\n"
            f"{'─' * 40}\n"
            f"💰 إجمالي المكافأة:      {reward:,.2f} ريال"
        )
    except Exception as e:
        return f"⚠️ خطأ في حساب مكافأة نهاية الخدمة: {e}"


@registry.register(
    description="البحث عن شركة في السعودية — بحث بالسجل التجاري أو الاسم التجاري",
    parameters={
        "query": {"type": "str", "description": "اسم الشركة أو رقم السجل التجاري"},
    },
)
async def company_search(query: str) -> str:
    """Search for a Saudi company by name or commercial registration number via web search."""
    try:
        from ddgs import DDGS
        search_query = f"منشأة {query} السعودية سجل تجاري"
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=5))
        if not results:
            search_query = f"{query} شركة السعودية"
            with DDGS() as ddgs:
                results = list(ddgs.text(search_query, max_results=5))
        if not results:
            return f"⚠️ لم يتم العثور على نتائج لـ '{query}'. حاول استخدام اسم أكثر تحديداً."
        lines = [
            f"🔍 نتائج البحث عن: {query}",
            "─" * 40,
        ]
        for i, r in enumerate(results, 1):
            title = r.get("title", "").strip()
            snippet = r.get("body", "").strip()[:250]
            url = r.get("href", "")
            lines.append(f"{i}. {title}")
            if snippet:
                lines.append(f"   {snippet}")
            lines.append(f"   🌐 {url}")
            lines.append("")
        return "\n".join(lines).strip()
    except ImportError:
        return "⚠️ البحث غير متاح: مكتبة duckduckgo_search غير مثبتة."
    except Exception as e:
        return f"⚠️ خطأ في البحث عن الشركة: {e}"


@registry.register(
    description="حاسبة نقطة التعادل — حساب عدد الوحدات والإيرادات المطلوبة لتحقيق التعادل",
    parameters={
        "fixed_costs": {"type": "number", "description": "التكاليف الثابتة (ريال)"},
        "variable_cost_per_unit": {"type": "number", "description": "التكلفة المتغيرة للوحدة (ريال)"},
        "selling_price_per_unit": {"type": "number", "description": "سعر بيع الوحدة (ريال)"},
    },
)
async def break_even(fixed_costs: float, variable_cost_per_unit: float, selling_price_per_unit: float) -> str:
    """Break-even point calculator. Returns break-even units and revenue."""
    try:
        if selling_price_per_unit <= variable_cost_per_unit:
            return "⚠️ سعر البيع يجب أن يكون أكبر من التكلفة المتغيرة للوحدة."
        contribution_margin = selling_price_per_unit - variable_cost_per_unit
        be_units = fixed_costs / contribution_margin
        be_revenue = be_units * selling_price_per_unit
        return (
            f"📊 حاسبة نقطة التعادل\n"
            f"{'─' * 35}\n"
            f"التكاليف الثابتة:           {fixed_costs:,.2f} ريال\n"
            f"التكلفة المتغيرة للوحدة:   {variable_cost_per_unit:,.2f} ريال\n"
            f"سعر بيع الوحدة:            {selling_price_per_unit:,.2f} ريال\n"
            f"هامش المساهمة:             {contribution_margin:,.2f} ريال\n"
            f"{'─' * 35}\n"
            f"نقطة التعادل بالوحدات:     {be_units:,.0f} وحدة\n"
            f"نقطة التعادل بالإيرادات:   {be_revenue:,.2f} ريال"
        )
    except Exception as e:
        return f"⚠️ خطأ في حساب نقطة التعادل: {e}"

# ─── Employee Directory ──────────────────────────────────────────
from tools.directory import search_employee as _search_emp, add_employee as _add_emp

@registry.register(
    description="Search employees by name, department, role, or phone. Use when asked about employee contact info, \"رقم فلان\", or \"من يعمل في قسم كذا\".",
    parameters={"query": {"type": "str", "description": "Search term (name, department, role, phone) — empty for all employees"}}
)
async def search_employee_tool(query: str = "") -> str:
    return await _search_emp(query)

@registry.register(
    description="Add a new employee to the company directory.",
    parameters={
        "name": {"type": "str", "description": "Full name"},
        "role": {"type": "str", "description": "Job title"},
        "department": {"type": "str", "description": "Department"},
        "phone": {"type": "str", "description": "Phone number"},
        "email": {"type": "str", "description": "Email"},
        "name_en": {"type": "str", "description": "English name (optional)"},
    }
)
async def add_employee_tool(name: str, role: str = "", department: str = "",
                            phone: str = "", email: str = "", name_en: str = "") -> str:
    return await _add_emp(name, role, department, phone, email, name_en)

