from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from calendar import month_name
from app.models import Account, Expense, User
from app import db

bp = Blueprint("accounting", __name__)

# ============================================================
# ВСПОМОГАТЕЛЬНОЕ: МСК-время
# ============================================================
MSK_OFFSET = timedelta(hours=3)

def now_msk():
    """Текущее время в МСК (UTC+3)"""
    return datetime.utcnow() + MSK_OFFSET


def month_range_msk(year, month):
    """Возвращает (начало, конец) месяца в UTC для фильтрации"""
    start_msk = datetime(year, month, 1)
    if month == 12:
        end_msk = datetime(year + 1, 1, 1)
    else:
        end_msk = datetime(year, month + 1, 1)
    # Конвертируем МСК → UTC (вычитаем 3 часа)
    return start_msk - MSK_OFFSET, end_msk - MSK_OFFSET


# ============================================================
# ГЛАВНАЯ БУХГАЛТЕРИИ
# ============================================================
@bp.route("/accounting")
@login_required
def index():
    # Только свои данные
    accounts = Account.query.filter_by(created_by=current_user.id).all()
    expenses = Expense.query.filter_by(created_by=current_user.id).all()

    # --- За всё время ---
    total_accounts = len(accounts)
    total_cost_accounts = sum(a.effective_cost for a in accounts)

    total_cost_email = sum(e.amount for e in expenses if e.category == "email")
    total_cost_proxy = sum(e.amount for e in expenses if e.category == "proxy")
    total_cost_other = sum(e.amount for e in expenses if e.category == "other")

    total_expenses = total_cost_accounts + total_cost_email + total_cost_proxy + total_cost_other

    sold_accounts = [a for a in accounts if a.sold and a.sold_price]
    total_income = sum(a.sold_price for a in sold_accounts)

    total_profit = total_income - total_expenses
    total_margin = (total_profit / total_income * 100) if total_income > 0 else 0

    # --- Месяцы ---
    now = now_msk()
    selected_month_str = request.args.get("month", f"{now.year}-{now.month:02d}")

    try:
        sel_year, sel_month = map(int, selected_month_str.split("-"))
    except ValueError:
        sel_year, sel_month = now.year, now.month
        selected_month_str = f"{now.year}-{now.month:02d}"

    # Считаем месяц
    month_data = calculate_month(accounts, expenses, sel_year, sel_month)

    # Список всех месяцев (все подряд от первого до текущего)
    all_months = build_all_months(accounts, expenses, now)

    # Данные для вкладки "По месяцам"
    months_table = []
    for y, m in all_months:
        md = calculate_month(accounts, expenses, y, m)
        months_table.append(md)

    return render_template(
        "accounting.html",
        # За всё время
        total_accounts=total_accounts,
        total_cost_accounts=total_cost_accounts,
        total_cost_email=total_cost_email,
        total_cost_proxy=total_cost_proxy,
        total_cost_other=total_cost_other,
        total_expenses=total_expenses,
        total_income=total_income,
        total_profit=total_profit,
        total_margin=total_margin,
        sold_count=len(sold_accounts),
        # Месяц
        month_data=month_data,
        selected_month_str=selected_month_str,
        # Таблица месяцев
        months_table=months_table,
        # Список расходов (свежие сверху)
        expenses_list=sorted(expenses, key=lambda e: e.date, reverse=True),
        # Доходы
        sold_accounts_list=sorted(sold_accounts, key=lambda a: a.sold_date or datetime.min, reverse=True),
    )


def calculate_month(accounts, expenses, year, month):
    """Считает цифры за конкретный месяц (МСК)"""
    start, end = month_range_msk(year, month)

    # Номера, созданные в этом месяце (по reg_date)
    accs_in_month = [
        a for a in accounts
        if a.reg_date and date(year, month, 1) <= a.reg_date < date(
            end.year, end.month, end.day if end.day > 1 else 1
        ) if True  # упростим
    ]
    # Правильнее по дате:
    from calendar import monthrange
    last_day = monthrange(year, month)[1]
    accs_in_month = [
        a for a in accounts
        if a.reg_date and a.reg_date.year == year and a.reg_date.month == month
    ]

    cost_accounts = sum(a.effective_cost for a in accs_in_month)

    exp_in_month = [
        e for e in expenses
        if e.date and e.date.year == year and e.date.month == month
    ]
    cost_email = sum(e.amount for e in exp_in_month if e.category == "email")
    cost_proxy = sum(e.amount for e in exp_in_month if e.category == "proxy")
    cost_other = sum(e.amount for e in exp_in_month if e.category == "other")

    total_expenses = cost_accounts + cost_email + cost_proxy + cost_other

    # Доход: продажи в этом месяце
    sold_in_month = [
        a for a in accounts
        if a.sold and a.sold_price and a.sold_date
        and (a.sold_date + MSK_OFFSET).year == year
        and (a.sold_date + MSK_OFFSET).month == month
    ]
    income = sum(a.sold_price for a in sold_in_month)
    profit = income - total_expenses
    margin = (profit / income * 100) if income > 0 else 0

    return {
        "year": year,
        "month": month,
        "label": f"{month_name[month]} {year}",
        "accounts_count": len(accs_in_month),
        "cost_accounts": cost_accounts,
        "cost_email": cost_email,
        "cost_proxy": cost_proxy,
        "cost_other": cost_other,
        "total_expenses": total_expenses,
        "income": income,
        "profit": profit,
        "margin": margin,
        "sold_count": len(sold_in_month),
    }


def build_all_months(accounts, expenses, now):
    """Список (year, month) от самого раннего события до текущего месяца"""
    dates = []
    for a in accounts:
        if a.reg_date:
            dates.append(a.reg_date)
        if a.sold_date:
            dates.append(a.sold_date.date())
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
# РАСХОДЫ: ДОБАВИТЬ
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

    e = Expense(
        date=exp_date,
        category=category,
        amount=amount,
        comment=comment,
        created_by=current_user.id,
    )
    db.session.add(e)
    db.session.commit()

    flash(f"Расход ${amount:.2f} добавлен", "success")
    return redirect(url_for("accounting.index"))


# ============================================================
# РАСХОДЫ: JSON (для редактирования)
# ============================================================
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


# ============================================================
# РАСХОДЫ: РЕДАКТИРОВАТЬ
# ============================================================
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


# ============================================================
# РАСХОДЫ: УДАЛИТЬ
# ============================================================
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