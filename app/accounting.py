from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from calendar import month_name

from app.models import Account, Expense
from app import db

bp = Blueprint("accounting", __name__)

# ============================================================
# МСК-время
# ============================================================
MSK_OFFSET = timedelta(hours=3)


def now_msk():
    return datetime.utcnow() + MSK_OFFSET


# ============================================================
# ГЛАВНАЯ БУХГАЛТЕРИИ
# ============================================================
@bp.route("/accounting")
@login_required
def index():
    accounts = Account.query.filter_by(created_by=current_user.id).all()
    expenses = Expense.query.filter_by(created_by=current_user.id).all()

    # ============================================================
    # РАЗДЕЛ 1: ПРОДАЖИ
    # ============================================================
    sold_accounts = [a for a in accounts if a.sold]

    # Доход от продаж
    total_sold_income = sum(a.sold_price or 0 for a in sold_accounts)

    # Расход: номера проданных
    total_sold_cost_accounts = sum(a.effective_cost for a in sold_accounts)

    # Расход: оплата проданных
    total_sold_payment = sum(a.payment_amount or 0 for a in sold_accounts)

    # Расход: ВСЕ ручные (почты, прокси, прочее) — идут в продажи
    total_manual_email = sum(e.amount for e in expenses if e.category == "email")
    total_manual_proxy = sum(e.amount for e in expenses if e.category == "proxy")
    total_manual_other = sum(e.amount for e in expenses if e.category == "other")
    total_manual = total_manual_email + total_manual_proxy + total_manual_other

    # Итого по продажам
    total_sold_expenses = total_sold_cost_accounts + total_sold_payment + total_manual
    total_sold_profit = total_sold_income - total_sold_expenses
    total_sold_margin = (total_sold_profit / total_sold_income * 100) if total_sold_income > 0 else 0

    # ============================================================
    # РАЗДЕЛ 2: ОТРАБОТАННЫЕ (WORK)
    # ============================================================
    work_accounts = [a for a in accounts if a.is_work]

    # Доход от работы
    total_work_income = sum(a.earned_amount or 0 for a in work_accounts)

    # Расход: номера WORK-аккаунтов
    total_work_cost_accounts = sum(a.effective_cost for a in work_accounts)

    # Расход: оплата WORK-аккаунтов
    total_work_payment = sum(a.payment_amount or 0 for a in work_accounts)

    # Итого по работе
    total_work_expenses = total_work_cost_accounts + total_work_payment
    total_work_profit = total_work_income - total_work_expenses
    total_work_margin = (total_work_profit / total_work_income * 100) if total_work_income > 0 else 0

    # ============================================================
    # ОБЩИЕ КАРТОЧКИ
    # ============================================================
    # Pending-оплата — общие расходы (не привязаны к продаже/работе)
    pending_accounts = [a for a in accounts if not a.sold and not a.is_work and a.payment_amount]
    total_pending_payment = sum(a.payment_amount or 0 for a in pending_accounts)

    total_income = total_sold_income + total_work_income
    total_expenses_all = total_sold_expenses + total_work_expenses + total_pending_payment
    total_profit_all = total_income - total_expenses_all
    total_margin_all = (total_profit_all / total_income * 100) if total_income > 0 else 0

    # ============================================================
    # МЕСЯЧНАЯ РАЗБИВКА (по МСК)
    # ============================================================
    now = now_msk()
    selected_month_str = request.args.get("month", f"{now.year}-{now.month:02d}")
    try:
        sel_year, sel_month = map(int, selected_month_str.split("-"))
    except ValueError:
        sel_year, sel_month = now.year, now.month
        selected_month_str = f"{now.year}-{now.month:02d}"

    # Продажи по месяцам
    sold_months = calculate_sold_months(accounts, expenses, now)

    # Отработанные по месяцам
    work_months = calculate_work_months(accounts, now)

    # Данные для выбранного месяца (детали)
    month_sold_data = calculate_month_sold(accounts, expenses, sel_year, sel_month)
    month_work_data = calculate_month_work(accounts, sel_year, sel_month)

    # Все месяцы для селекта
    all_months = build_all_months(accounts, expenses, now)

    return render_template(
        "accounting.html",
        # Продажи (за всё время)
        total_sold_income=total_sold_income,
        total_sold_cost_accounts=total_sold_cost_accounts,
        total_sold_payment=total_sold_payment,
        total_manual_email=total_manual_email,
        total_manual_proxy=total_manual_proxy,
        total_manual_other=total_manual_other,
        total_manual=total_manual,
        total_sold_expenses=total_sold_expenses,
        total_sold_profit=total_sold_profit,
        total_sold_margin=total_sold_margin,
        sold_count=len(sold_accounts),

        # Работа (за всё время)
        total_work_income=total_work_income,
        total_work_cost_accounts=total_work_cost_accounts,
        total_work_payment=total_work_payment,
        total_work_expenses=total_work_expenses,
        total_work_profit=total_work_profit,
        total_work_margin=total_work_margin,
        work_count=len(work_accounts),

        # Общие
        total_income=total_income,
        total_expenses_all=total_expenses_all,
        total_profit_all=total_profit_all,
        total_margin_all=total_margin_all,
        total_pending_payment=total_pending_payment,

        # Месячная разбивка
        sold_months=sold_months,
        work_months=work_months,
        month_sold_data=month_sold_data,
        month_work_data=month_work_data,
        selected_month_str=selected_month_str,
        all_months=all_months,

        # Списки
        expenses_list=sorted(expenses, key=lambda e: e.date, reverse=True),
        sold_accounts_list=sorted(sold_accounts, key=lambda a: a.sold_date or datetime.min, reverse=True),
    )


# ============================================================
# РАСЧЁТЫ ПО ПРОДАЖАМ
# ============================================================
def calculate_month_sold(accounts, expenses, year, month):
    """Расчёт продаж за месяц"""
    accs_in_month = [
        a for a in accounts
        if a.sold and a.sold_price and a.sold_date
        and (a.sold_date + MSK_OFFSET).year == year
        and (a.sold_date + MSK_OFFSET).month == month
    ]
    income = sum(a.sold_price or 0 for a in accs_in_month)
    cost_accounts = sum(a.effective_cost for a in accs_in_month)
    payment = sum(a.payment_amount or 0 for a in accs_in_month)

    # Ручные расходы за этот месяц
    exp_in_month = [
        e for e in expenses
        if e.date and e.date.year == year and e.date.month == month
    ]
    cost_email = sum(e.amount for e in exp_in_month if e.category == "email")
    cost_proxy = sum(e.amount for e in exp_in_month if e.category == "proxy")
    cost_other = sum(e.amount for e in exp_in_month if e.category == "other")

    total_exp = cost_accounts + payment + cost_email + cost_proxy + cost_other
    profit = income - total_exp
    margin = (profit / income * 100) if income > 0 else 0

    return {
        "year": year, "month": month,
        "label": f"{month_name[month]} {year}",
        "count": len(accs_in_month),
        "income": income,
        "cost_accounts": cost_accounts,
        "payment": payment,
        "cost_email": cost_email,
        "cost_proxy": cost_proxy,
        "cost_other": cost_other,
        "total_exp": total_exp,
        "profit": profit,
        "margin": margin,
    }


def calculate_sold_months(accounts, expenses, now):
    """Все месяцы для продаж"""
    dates = []
    for a in accounts:
        if a.sold and a.sold_date:
            dates.append((a.sold_date + MSK_OFFSET).date())
    for e in expenses:
        if e.date:
            dates.append(e.date)

    if not dates:
        return []

    earliest = min(dates)
    months = []
    y, m = earliest.year, earliest.month
    while (y, m) <= (now.year, now.month):
        months.append(calculate_month_sold(accounts, expenses, y, m))
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return months


# ============================================================
# РАСЧЁТЫ ПО РАБОТЕ
# ============================================================
def calculate_month_work(accounts, year, month):
    """Расчёт работы за месяц"""
    # Доход считаем по work_started_at (когда поставили WORK)
    accs_in_month = [
        a for a in accounts
        if a.is_work and a.earned_amount and a.work_started_at
        and (a.work_started_at + MSK_OFFSET).year == year
        and (a.work_started_at + MSK_OFFSET).month == month
    ]
    income = sum(a.earned_amount or 0 for a in accs_in_month)

    # Расход: номера (по reg_date!) и оплата
    accs_reg_in_month = [
        a for a in accounts
        if a.is_work and a.reg_date
        and a.reg_date.year == year and a.reg_date.month == month
    ]
    cost_accounts = sum(a.effective_cost for a in accs_reg_in_month)
    payment = sum(a.payment_amount or 0 for a in accs_reg_in_month)

    total_exp = cost_accounts + payment
    profit = income - total_exp
    margin = (profit / income * 100) if income > 0 else 0

    return {
        "year": year, "month": month,
        "label": f"{month_name[month]} {year}",
        "count": len(accs_in_month),
        "income": income,
        "cost_accounts": cost_accounts,
        "payment": payment,
        "total_exp": total_exp,
        "profit": profit,
        "margin": margin,
    }


def calculate_work_months(accounts, now):
    """Все месяцы для работы"""
    dates = []
    for a in accounts:
        if a.reg_date:
            dates.append(a.reg_date)
        if a.is_work and a.work_started_at:
            dates.append((a.work_started_at + MSK_OFFSET).date())

    if not dates:
        return []

    earliest = min(dates)
    months = []
    y, m = earliest.year, earliest.month
    while (y, m) <= (now.year, now.month):
        months.append(calculate_month_work(accounts, y, m))
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return months


def build_all_months(accounts, expenses, now):
    """Все месяцы для селекта"""
    dates = []
    for a in accounts:
        if a.reg_date:
            dates.append(a.reg_date)
        if a.sold_date:
            dates.append((a.sold_date + MSK_OFFSET).date())
        if a.work_started_at:
            dates.append((a.work_started_at + MSK_OFFSET).date())
    for e in expenses:
        if e.date:
            dates.append(e.date)

    if not dates:
        return [(now.year, now.month)]

    earliest = min(dates)
    months = []
    y, m = earliest.year, earliest.month
    while (y, m) <= (now.year, now.month):
        months.append((y, m))
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return months


# ============================================================
# РАСХОДЫ: CRUD (без изменений)
# ============================================================
@bp.route("/expenses/add", methods=["POST"])
@login_required
def expense_add():
    date_str = request.form.get("date", "").strip()
    category = request.form.get("category", "").strip()
    amount_str = request.form.get("amount", "").strip()
    comment = request.form.get("comment", "").strip() or None

    if not date_str or not category or not amount_str:
        flash("Заполни дату, категорию и сумму", "danger")
        return redirect(url_for("accounting.index"))

    if category not in ("email", "proxy", "other"):
        flash("Неверная категория", "danger")
        return redirect(url_for("accounting.index"))

    try:
        exp_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        amount = float(amount_str)
    except ValueError:
        flash("Неверный формат даты или суммы", "danger")
        return redirect(url_for("accounting.index"))

    e = Expense(date=exp_date, category=category, amount=amount,
                comment=comment, created_by=current_user.id)
    db.session.add(e)
    db.session.commit()
    flash(f"Расход ${amount:.2f} добавлен", "success")
    return redirect(url_for("accounting.index"))


@bp.route("/expenses/<int:exp_id>/json")
@login_required
def expense_json(exp_id):
    e = Expense.query.get_or_404(exp_id)
    if e.created_by != current_user.id:
        return {"error": "forbidden"}, 403
    return {
        "id": e.id,
        "date": e.date.strftime("%Y-%m-%d") if e.date else "",
        "category": e.category,
        "amount": e.amount,
        "comment": e.comment or "",
    }


@bp.route("/expenses/<int:exp_id>/edit", methods=["POST"])
@login_required
def expense_edit(exp_id):
    e = Expense.query.get_or_404(exp_id)
    if e.created_by != current_user.id:
        flash("Можно редактировать только свои расходы", "danger")
        return redirect(url_for("accounting.index"))

    date_str = request.form.get("date", "").strip()
    category = request.form.get("category", "").strip()
    amount_str = request.form.get("amount", "").strip()
    comment = request.form.get("comment", "").strip() or None

    try:
        e.date = datetime.strptime(date_str, "%Y-%m-%d").date()
        e.amount = float(amount_str)
    except ValueError:
        flash("Неверный формат", "danger")
        return redirect(url_for("accounting.index"))

    e.category = category
    e.comment = comment
    db.session.commit()
    flash("Расход обновлён", "success")
    return redirect(url_for("accounting.index"))


@bp.route("/expenses/<int:exp_id>/delete", methods=["POST"])
@login_required
def expense_delete(exp_id):
    e = Expense.query.get_or_404(exp_id)
    if e.created_by != current_user.id:
        flash("Можно удалять только свои расходы", "danger")
        return redirect(url_for("accounting.index"))
    db.session.delete(e)
    db.session.commit()
    flash("Расход удалён", "warning")
    return redirect(url_for("accounting.index"))