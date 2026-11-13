from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from datetime import datetime

from app.models import Account, Log, Unsubscribe, SupportTicket, StatusHistory
from app import db

bp = Blueprint("routes", __name__)


# ============================================================
# ГЛАВНАЯ
# ============================================================
@bp.route("/")
@login_required
def index():
    tab = request.args.get("tab", "working")
    q = request.args.get("q", "").strip()
    sort_by = request.args.get("sort", "reg_date")
    user_filter = request.args.get("user_filter", "mine").strip()

    # --- Новые фильтры ---
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    filter_statuses = request.args.getlist("status")  # список
    filter_devices = request.args.getlist("device")   # android / iphone11 / iphone15
    filter_payment = request.args.get("payment", "")  # "" / "yes" / "no"
    filter_screens = request.args.get("screens", "")  # "" / "yes" / "no"

    # --- Базовый запрос ---
    query = Account.query

    # --- Права ---
    is_admin = (current_user.role == "admin")
    can_view_others = is_admin or current_user.can_view_others
    can_edit_others = is_admin or current_user.can_edit_others

    if not can_view_others:
        query = query.filter(Account.created_by == current_user.id)
    elif user_filter:
        if user_filter == "mine":
            query = query.filter(Account.created_by == current_user.id)
        elif user_filter != "all":
            try:
                uid = int(user_filter)
                query = query.filter(Account.created_by == uid)
            except ValueError:
                pass

    # --- Поиск ---
    if q:
        query = query.filter(
            (Account.email.ilike(f"%{q}%")) | (Account.nick.ilike(f"%{q}%"))
        )

    # --- Фильтр по дате ---
    if date_from:
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            query = query.filter(Account.reg_date >= d_from)
        except ValueError:
            pass
    if date_to:
        try:
            d_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            query = query.filter(Account.reg_date <= d_to)
        except ValueError:
            pass

    # --- Фильтр по статусам ---
    if filter_statuses:
        query = query.filter(Account.status.in_(filter_statuses))

    # --- Фильтр по устройствам ---
    if filter_devices:
        from sqlalchemy import or_
        conditions = []
        if "android" in filter_devices:
            conditions.append(Account.device_android == True)
        if "iphone11" in filter_devices:
            conditions.append(Account.device_iphone11 == True)
        if "iphone15" in filter_devices:
            conditions.append(Account.device_iphone15 == True)
        if conditions:
            query = query.filter(or_(*conditions))

    # --- Оплата ---
    if filter_payment == "yes":
        query = query.filter(Account.payment_sent == True)
    elif filter_payment == "no":
        query = query.filter(Account.payment_sent == False)

    # --- Скрины (есть в любом тикете) ---
    if filter_screens:
        subq_has = db.session.query(SupportTicket.account_id).filter(SupportTicket.screens_sent == True)
        if filter_screens == "yes":
            query = query.filter(Account.id.in_(subq_has))
        elif filter_screens == "no":
            query = query.filter(~Account.id.in_(subq_has))

    # --- Сортировка ---
    if sort_by == "status":
        query = query.order_by(Account.status.asc())
    elif sort_by == "email":
        query = query.order_by(Account.email.asc())
    else:
        query = query.order_by(Account.reg_date.desc())

    all_accounts = query.all()

    # --- Вкладки (5 штук) ---
    work    = [a for a in all_accounts if a.is_work_tab]
    working = [a for a in all_accounts if a.is_working_tab]
    pending = [a for a in all_accounts if a.is_pending_tab]
    sold    = [a for a in all_accounts if a.is_sold_tab]
    invalid = [a for a in all_accounts if a.is_invalid_tab]

    # --- Список юзеров ---
    users_for_filter = []
    if can_view_others:
        from app.models import User
        users_for_filter = User.query.order_by(User.username.asc()).all()

    # --- Активные фильтры (для подсветки кнопки) ---
    has_active_filters = bool(
        date_from or date_to or filter_statuses or filter_devices
        or filter_payment or filter_screens or sort_by != "reg_date"
    )

    return render_template(
        "index.html",
        tab=tab, q=q, sort_by=sort_by, user_filter=user_filter,
        date_from=date_from, date_to=date_to,
        filter_statuses=filter_statuses,
        filter_devices=filter_devices,
        filter_payment=filter_payment,
        filter_screens=filter_screens,
        has_active_filters=has_active_filters,
        users_for_filter=users_for_filter,
        can_view_others=can_view_others,
        can_edit_others=can_edit_others,
        work=work, working=working, pending=pending, sold=sold, invalid=invalid,
        work_count=len(work), working_count=len(working), pending_count=len(pending),
        sold_count=len(sold), invalid_count=len(invalid),
    )


# ============================================================
# ДОБАВЛЕНИЕ АККАУНТА
# ============================================================
@bp.route("/account/add", methods=["POST"])
@login_required
def account_add():
    reg_date_str = request.form.get("reg_date")
    reg_time = request.form.get("reg_time") or None
    email = request.form.get("email", "").strip()
    email_password = request.form.get("email_password", "").strip()
    nick = request.form.get("nick", "").strip() or None
    account_password = request.form.get("account_password", "").strip()
    phone = request.form.get("phone", "").strip() or None
    status = request.form.get("status", "online")

    if not reg_date_str or not email or not email_password or not account_password:
        flash("Заполните все обязательные поля!", "danger")
        return redirect(url_for("routes.index"))

    try:
        reg_date = datetime.strptime(reg_date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Неверный формат даты", "danger")
        return redirect(url_for("routes.index"))

    cost_str = request.form.get("cost_amount", "").strip()
    try:
        cost_amount = float(cost_str) if cost_str else None
    except ValueError:
        cost_amount = None

    a = Account(
        reg_date=reg_date,
        reg_time=reg_time,
        email=email,
        email_password=email_password,
        nick=nick,
        account_password=account_password,
        phone=phone,
        status=status,
        cost_amount=cost_amount,
        created_by=current_user.id,
    )

    # --- Support (простые поля) ---
    a.payment_sent = request.form.get("payment_sent") == "on"
    a.is_on_pc = request.form.get("is_on_pc") == "on"

    # --- Устройство ---
    a.device_android = request.form.get("device_android") == "on"
    a.device_iphone11 = request.form.get("device_iphone11") == "on"
    a.device_iphone15 = request.form.get("device_iphone15") == "on"

    # --- ТОП ---
    a.is_top = request.form.get("is_top") == "on"

    # --- Работа ---
    a.is_work = request.form.get("is_work") == "on"
    earned_str = request.form.get("earned_amount", "").strip()
    try:
        a.earned_amount = float(earned_str) if earned_str else None
    except ValueError:
        a.earned_amount = None
    if a.is_work:
        a.work_started_at = datetime.utcnow()

    # --- Оплата (сумма) ---
    pay_str = request.form.get("payment_amount", "").strip()
    try:
        a.payment_amount = float(pay_str) if pay_str else None
    except ValueError:
        a.payment_amount = None
    # Если сумма указана — галка автоматически
    if a.payment_amount and a.payment_amount > 0:
        a.payment_sent = True

    if status == "SALE":
        a.sold = True
        a.sold_date = datetime.utcnow()
    if status == "Pending TOP":
        a.pending_since = datetime.utcnow()

    db.session.add(a)
    db.session.flush()  # чтобы получить a.id до commit

    # История статусов (первая запись)
    history = StatusHistory(
        account_id=a.id,
        old_status=None,
        new_status=a.status,
        changed_by=current_user.id,
        changed_by_username=current_user.username,
    )
    db.session.add(history)

    db.session.commit()

    log = Log(
        user_id=current_user.id,
        username=current_user.username,
        action="create_account",
        target=email,
        details=f"Статус: {status}",
    )
    db.session.add(log)
    db.session.commit()

    flash(f"Аккаунт {email} добавлен", "success")
    current_tab = request.form.get("current_tab", "working")
    return redirect(url_for("routes.index", tab=current_tab))


# ============================================================
# JSON ДАННЫХ АККАУНТА (для модалки и тултипа)
# ============================================================
@bp.route("/account/<int:acc_id>/json")
@login_required
def account_json(acc_id):
    a = Account.query.get_or_404(acc_id)

    return {
        "id": a.id,
        "reg_date": a.reg_date.strftime("%Y-%m-%d") if a.reg_date else "",
        "reg_time": a.reg_time or "",
        "email": a.email or "",
        "email_password": a.email_password or "",
        "nick": a.nick or "",
        "account_password": a.account_password or "",
        "phone": a.phone or "",
        "status": a.status or "online",
        "is_top": a.is_top,
        "for_sale": a.for_sale,
        "sold": a.sold,
        "sold_price": a.sold_price or "",
        "sold_date": a.sold_date.strftime("%Y-%m-%d %H:%M") if a.sold_date else "",
        "has_cookies": bool(a.cookies_text),
        "cookies_text": a.cookies_text or "",
        "is_on_pc": a.is_on_pc,
        "payment_sent": a.payment_sent,
        "is_work": a.is_work,
        "earned_amount": a.earned_amount if a.earned_amount is not None else "",
        "payment_amount": a.payment_amount if a.payment_amount is not None else "",
        "device_android": a.device_android,
        "device_iphone11": a.device_iphone11,
        "device_iphone15": a.device_iphone15,
        "tickets": [
            {
                "id": t.id,
                "letter_number": t.letter_number,
                "sent_date": t.sent_date.strftime("%Y-%m-%d") if t.sent_date else "",
                "text": t.text or "",
                "screens_sent": t.screens_sent,
                "outcome": t.outcome,
                "resolved_date": t.resolved_date.strftime("%Y-%m-%d") if t.resolved_date else "",
            }
            for t in sorted(a.support_tickets, key=lambda x: x.letter_number)
        ],
        "support_result_display": a.support_result_display or "",
        "support_days": a.support_days,
        "status_history": [
            {
                "old_status": h.old_status or "—",
                "new_status": h.new_status,
                "changed_at": h.changed_at.strftime("%d.%m.%Y %H:%M"),
                "changed_by": h.changed_by_username or "—",
            }
            for h in a.status_history_display
        ],
        "comment": a.comment or "",
        "cost_amount": a.cost_amount if a.cost_amount is not None else "",
        "created_by": a.created_by or 0,
        "creator_username": a.creator_username,
    }


# ============================================================
# СОХРАНЕНИЕ ИЗМЕНЕНИЙ АККАУНТА
# ============================================================
@bp.route("/account/<int:acc_id>/edit", methods=["POST"])
@login_required
def account_edit(acc_id):
    a = Account.query.get_or_404(acc_id)

    # Проверка прав
    is_admin = (current_user.role == "admin")
    can_edit_others = is_admin or current_user.can_edit_others
    if a.created_by != current_user.id and not can_edit_others:
        flash("Нет прав редактировать этот аккаунт", "danger")
        return redirect(url_for("routes.index"))

    old_status = a.status

    a.reg_date = datetime.strptime(request.form["reg_date"], "%Y-%m-%d").date()
    a.reg_time = request.form.get("reg_time") or None
    a.email = request.form.get("email", "").strip()
    a.email_password = request.form.get("email_password", "").strip()
    a.nick = request.form.get("nick", "").strip() or None
    a.account_password = request.form.get("account_password", "").strip()
    a.phone = request.form.get("phone", "").strip() or None
    a.status = request.form.get("status", "online")
    a.comment = request.form.get("comment", "").strip() or None
    cost_str = request.form.get("cost_amount", "").strip()
    try:
        a.cost_amount = float(cost_str) if cost_str else None
    except ValueError:
        a.cost_amount = None

    # --- Продажа ---
    a.for_sale = request.form.get("for_sale") == "on"
    price_str = request.form.get("sold_price", "").strip()
    try:
        a.sold_price = float(price_str) if price_str else None
    except ValueError:
        a.sold_price = None

    # Логика при смене статуса
    if a.status == "Pending TOP" and old_status != "Pending TOP":
        a.pending_since = datetime.utcnow()
    elif a.status != "Pending TOP":
        a.pending_since = None

    if a.status == "SALE":
        a.sold = True
        if not a.sold_date:
            a.sold_date = datetime.utcnow()
    else:
        a.sold = False
        a.sold_date = None

    # --- Support (простые поля) ---
    a.is_on_pc = request.form.get("is_on_pc") == "on"
    a.payment_sent = request.form.get("payment_sent") == "on"

    # --- Устройство ---
    a.device_android = request.form.get("device_android") == "on"
    a.device_iphone11 = request.form.get("device_iphone11") == "on"
    a.device_iphone15 = request.form.get("device_iphone15") == "on"

    # --- ТОП ---
    a.is_top = request.form.get("is_top") == "on"

    # --- Работа ---
    old_is_work = a.is_work
    a.is_work = request.form.get("is_work") == "on"
    earned_str = request.form.get("earned_amount", "").strip()
    try:
        a.earned_amount = float(earned_str) if earned_str else None
    except ValueError:
        a.earned_amount = None

    # Если только что поставили WORK — фиксируем время
    if a.is_work and not old_is_work:
        a.work_started_at = datetime.utcnow()
    elif not a.is_work:
        a.work_started_at = None

    # --- Оплата (сумма) ---
    pay_str = request.form.get("payment_amount", "").strip()
    try:
        a.payment_amount = float(pay_str) if pay_str else None
    except ValueError:
        a.payment_amount = None
    # Если сумма указана — галка автоматически
    if a.payment_amount and a.payment_amount > 0:
        a.payment_sent = True

    # --- Куки ---
    if "cookies_text" in request.form:
        cookies = request.form["cookies_text"].strip()
        a.cookies_text = cookies if cookies else None

    # --- История статусов ---
    if old_status != a.status:
        history = StatusHistory(
            account_id=a.id,
            old_status=old_status,
            new_status=a.status,
            changed_by=current_user.id,
            changed_by_username=current_user.username,
        )
        db.session.add(history)

    db.session.commit()

    # Лог
    changes = []
    if old_status != a.status:
        changes.append(f"Статус: {old_status} → {a.status}")
    if a.sold:
        changes.append("Продан")

    log = Log(
        user_id=current_user.id,
        username=current_user.username,
        action="edit_account",
        target=a.email,
        details="; ".join(changes) if changes else "Изменения",
    )
    db.session.add(log)
    db.session.commit()

    flash(f"Аккаунт {a.email} обновлён", "success")
    # Сохраняем текущую вкладку
    current_tab = request.form.get("current_tab", "working")
    return redirect(url_for("routes.index", tab=current_tab))


# ============================================================
# КУКИ: СКАЧАТЬ
# ============================================================
@bp.route("/account/<int:acc_id>/cookies/download")
@login_required
def cookies_download(acc_id):
    a = Account.query.get_or_404(acc_id)

    if not a.cookies_text:
        flash("У этого аккаунта нет куки", "warning")
        return redirect(url_for("routes.index"))

    # Имя файла
    safe_email = a.email.replace("@", "_at_").replace(".", "_")
    safe_pass = a.email_password.replace("/", "_").replace("\\", "_")
    date_str = a.reg_date.strftime("%Y-%m-%d") if a.reg_date else "no-date"
    filename = f"{safe_email}_{safe_pass}_{date_str}.txt"

    # Шапка: легенда + данные
    header = (
        "log:pass\n"
        "mail:pass\n"
        "\n"
        f"{a.email}:{a.account_password}\n"
        f"{a.email}:{a.email_password}\n"
        "\n"
    )

    full_text = header + a.cookies_text

    log = Log(
        user_id=current_user.id,
        username=current_user.username,
        action="download_cookies",
        target=a.email,
        details="",
    )
    db.session.add(log)
    db.session.commit()

    return Response(
        full_text,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ============================================================
# КУКИ: УДАЛИТЬ
# ============================================================
@bp.route("/account/<int:acc_id>/cookies/delete", methods=["POST"])
@login_required
def cookies_delete(acc_id):
    a = Account.query.get_or_404(acc_id)
    a.cookies_text = None
    db.session.commit()

    log = Log(
        user_id=current_user.id,
        username=current_user.username,
        action="delete_cookies",
        target=a.email,
        details="",
    )
    db.session.add(log)
    db.session.commit()

    flash(f"Куки аккаунта {a.email} удалены", "warning")
    return redirect(url_for("routes.index"))


# ============================================================
# ОТПИСКИ: СПИСОК
# ============================================================
@bp.route("/account/<int:acc_id>/unsubs/json")
@login_required
def unsubs_json(acc_id):
    a = Account.query.get_or_404(acc_id)

    return [
        {
            "id": u.id,
            "email": u.email or "",
            "date": u.date.strftime("%Y-%m-%d") if u.date else "",
            "time": u.time or "",
            "comment": u.comment or "",
        }
        for u in a.unsubscribes
    ]


# ============================================================
# ОТПИСКИ: ДОБАВИТЬ
# ============================================================
@bp.route("/account/<int:acc_id>/unsubs/add", methods=["POST"])
@login_required
def unsubs_add(acc_id):
    a = Account.query.get_or_404(acc_id)

    email = request.form.get("email", "").strip() or None
    date_str = request.form.get("date", "").strip()
    time_str = request.form.get("time", "").strip() or None
    comment = request.form.get("comment", "").strip() or None

    unsub_date = None
    if date_str:
        try:
            unsub_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    u = Unsubscribe(
        account_id=a.id,
        email=email,
        date=unsub_date,
        time=time_str,
        comment=comment,
    )
    db.session.add(u)
    db.session.commit()

    log = Log(
        user_id=current_user.id,
        username=current_user.username,
        action="add_unsubscribe",
        target=a.email,
        details=f"Собеседник: {email}, {date_str} {time_str or ''}",
    )
    db.session.add(log)
    db.session.commit()

    return {"ok": True, "id": u.id}


# ============================================================
# ОТПИСКИ: УДАЛИТЬ
# ============================================================
@bp.route("/unsubs/<int:unsub_id>/delete", methods=["POST"])
@login_required
def unsubs_delete(unsub_id):
    u = Unsubscribe.query.get_or_404(unsub_id)
    acc_email = u.account.email if u.account else ""
    db.session.delete(u)
    db.session.commit()

    log = Log(
        user_id=current_user.id,
        username=current_user.username,
        action="delete_unsubscribe",
        target=acc_email,
        details=f"ID отписки: {unsub_id}",
    )
    db.session.add(log)
    db.session.commit()

    return {"ok": True}


# ============================================================
# ЛОГИ
# ============================================================
@bp.route("/logs")
@login_required
def logs():
    user_filter = request.args.get("user", "").strip()
    action_filter = request.args.get("action", "").strip()

    query = Log.query

    if user_filter:
        query = query.filter(Log.username.ilike(f"%{user_filter}%"))
    if action_filter:
        query = query.filter(Log.action == action_filter)

    logs_list = query.order_by(Log.created_at.desc()).limit(500).all()
    all_actions = [r[0] for r in db.session.query(Log.action).distinct().all()]

    return render_template(
        "logs.html",
        logs=logs_list,
        user_filter=user_filter,
        action_filter=action_filter,
        all_actions=all_actions,
    )


# ============================================================
# УДАЛЕНИЕ АККАУНТА
# ============================================================
@bp.route("/account/<int:acc_id>/delete", methods=["POST"])
@login_required
def account_delete(acc_id):
    a = Account.query.get_or_404(acc_id)

    is_admin = (current_user.role == "admin")
    can_edit_others = is_admin or current_user.can_edit_others

    if a.created_by != current_user.id and not can_edit_others:
        flash("Нет прав удалить этот аккаунт", "danger")
        return redirect(url_for("routes.index"))

    email = a.email

    # Жёсткое удаление (каскадно удалит unsubscribes благодаря relationship)
    db.session.delete(a)
    db.session.commit()

    # Лог
    log = Log(
        user_id=current_user.id,
        username=current_user.username,
        action="delete_account",
        target=email,
        details="Аккаунт удалён",
    )
    db.session.add(log)
    db.session.commit()

    flash(f"Аккаунт {email} удалён", "warning")
    return redirect(url_for("routes.index"))


# ============================================================
# ТИКЕТЫ: ДОБАВИТЬ
# ============================================================
@bp.route("/account/<int:acc_id>/ticket/add", methods=["POST"])
@login_required
def ticket_add(acc_id):
    a = Account.query.get_or_404(acc_id)

    is_admin = (current_user.role == "admin")
    can_edit_others = is_admin or current_user.can_edit_others
    if a.created_by != current_user.id and not can_edit_others:
        return {"error": "forbidden"}, 403

    if len(a.support_tickets) >= 5:
        return {"error": "max_tickets"}, 400

    sent_date_str = request.form.get("sent_date", "").strip()
    if not sent_date_str:
        return {"error": "no_date"}, 400

    try:
        sent_date = datetime.strptime(sent_date_str, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "bad_date"}, 400

    next_number = 1
    if a.support_tickets:
        next_number = max(t.letter_number for t in a.support_tickets) + 1

    outcome = request.form.get("outcome", "pending")
    resolved_date_str = request.form.get("resolved_date", "").strip()
    resolved_date = None
    if resolved_date_str and outcome != "pending":
        try:
            resolved_date = datetime.strptime(resolved_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    t = SupportTicket(
        account_id=a.id,
        letter_number=next_number,
        sent_date=sent_date,
        text=request.form.get("text", "").strip() or None,
        screens_sent=request.form.get("screens_sent") == "on",
        outcome=outcome,
        resolved_date=resolved_date,
    )
    db.session.add(t)
    db.session.commit()

    return {"ok": True, "id": t.id}


# ============================================================
# ТИКЕТЫ: РЕДАКТИРОВАТЬ
# ============================================================
@bp.route("/ticket/<int:ticket_id>/edit", methods=["POST"])
@login_required
def ticket_edit(ticket_id):
    t = SupportTicket.query.get_or_404(ticket_id)
    a = t.account

    is_admin = (current_user.role == "admin")
    can_edit_others = is_admin or current_user.can_edit_others
    if a.created_by != current_user.id and not can_edit_others:
        return {"error": "forbidden"}, 403

    sent_date_str = request.form.get("sent_date", "").strip()
    if sent_date_str:
        try:
            t.sent_date = datetime.strptime(sent_date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    t.text = request.form.get("text", "").strip() or None
    t.screens_sent = request.form.get("screens_sent") == "on"
    t.outcome = request.form.get("outcome", "pending")

    resolved_date_str = request.form.get("resolved_date", "").strip()
    if resolved_date_str and t.outcome != "pending":
        try:
            t.resolved_date = datetime.strptime(resolved_date_str, "%Y-%m-%d").date()
        except ValueError:
            t.resolved_date = None
    else:
        t.resolved_date = None

    db.session.commit()
    return {"ok": True}


# ============================================================
# ТИКЕТЫ: УДАЛИТЬ
# ============================================================
@bp.route("/ticket/<int:ticket_id>/delete", methods=["POST"])
@login_required
def ticket_delete(ticket_id):
    t = SupportTicket.query.get_or_404(ticket_id)
    a = t.account

    is_admin = (current_user.role == "admin")
    can_edit_others = is_admin or current_user.can_edit_others
    if a.created_by != current_user.id and not can_edit_others:
        return {"error": "forbidden"}, 403

    db.session.delete(t)
    db.session.commit()
    return {"ok": True}


# ============================================================
# ВЫГРУЗКА СТАТИСТИКИ В EXCEL
# ============================================================
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


@bp.route("/export/excel", methods=["POST"])
@login_required
def export_excel():
    # --- Права ---
    is_admin = (current_user.role == "admin")
    can_view_others = is_admin or current_user.can_view_others

    # --- Фильтры ---
    user_filter = request.form.get("user_filter", "").strip()
    date_from_str = request.form.get("date_from", "").strip()
    date_to_str = request.form.get("date_to", "").strip()
    statuses = request.form.getlist("status")  # список выбранных статусов

    query = Account.query

    # Права
    if not can_view_others:
        query = query.filter(Account.created_by == current_user.id)
    elif user_filter and user_filter != "all":
        try:
            uid = int(user_filter)
            query = query.filter(Account.created_by == uid)
        except ValueError:
            pass

    # Дата регистрации
    if date_from_str:
        try:
            d_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
            query = query.filter(Account.reg_date >= d_from)
        except ValueError:
            pass
    if date_to_str:
        try:
            d_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()
            query = query.filter(Account.reg_date <= d_to)
        except ValueError:
            pass

    # Статусы
    if statuses:
        query = query.filter(Account.status.in_(statuses))

    accounts = query.order_by(Account.reg_date.desc()).all()

    # --- Генерация Excel ---
    wb = Workbook()
    ws = wb.active
    ws.title = "Аккаунты"

    headers = [
        "Дата регистрации", "Email", "Телефон", "Стоимость номера ($)",
        "Текущий статус", "ТОП", "История статусов",
        "Комментарий к аккаунту",
        "Оплата отправлена",
    ]
    # Тикеты — 5 штук по 5 колонок
    for i in range(1, 6):
        headers += [
            f"Тикет {i}: дата", f"Тикет {i}: скрины", f"Тикет {i}: текст",
            f"Тикет {i}: результат", f"Тикет {i}: дата решения"
        ]
    # Дополнительно
    headers.append("Дней между 1 и 2 письмом")

    # Заголовки
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="4B0082")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Данные
    for row_idx, a in enumerate(accounts, 2):
        # История
        history_str = "; ".join([
            f"{h.changed_at.strftime('%d.%m.%Y')}: {h.old_status or '—'}→{h.new_status}"
            for h in a.status_history_display
        ])

        col = 1
        ws.cell(row=row_idx, column=col, value=a.reg_date.strftime("%d.%m.%Y") if a.reg_date else ""); col += 1
        ws.cell(row=row_idx, column=col, value=a.email or ""); col += 1
        ws.cell(row=row_idx, column=col, value=a.phone or ""); col += 1
        ws.cell(row=row_idx, column=col, value=a.cost_amount if a.cost_amount is not None else 2.0); col += 1
        ws.cell(row=row_idx, column=col, value=a.status or ""); col += 1
        ws.cell(row=row_idx, column=col, value="👑" if a.is_top else ""); col += 1
        ws.cell(row=row_idx, column=col, value=history_str); col += 1
        ws.cell(row=row_idx, column=col, value=a.comment or ""); col += 1
        ws.cell(row=row_idx, column=col, value="Да" if a.payment_sent else "Нет"); col += 1

        # Сортируем тикеты
        tickets = sorted(a.support_tickets, key=lambda t: t.letter_number)

        for i in range(5):
            if i < len(tickets):
                t = tickets[i]
                outcome_text = {
                    "pending": "⏳ Ожидание",
                    "unlocked": "✅ UNLOCK",
                    "all_gesperrt": "❌ ALL Gesperrt",
                }.get(t.outcome, t.outcome)
                ws.cell(row=row_idx, column=col, value=t.sent_date.strftime("%d.%m.%Y") if t.sent_date else ""); col += 1
                ws.cell(row=row_idx, column=col, value="Да" if t.screens_sent else "Нет"); col += 1
                ws.cell(row=row_idx, column=col, value=t.text or ""); col += 1
                ws.cell(row=row_idx, column=col, value=outcome_text); col += 1
                ws.cell(row=row_idx, column=col, value=t.resolved_date.strftime("%d.%m.%Y") if t.resolved_date else ""); col += 1
            else:
                for _ in range(5):
                    ws.cell(row=row_idx, column=col, value=""); col += 1

        # Дней между тикет 1 и 2
        days_between = ""
        if len(tickets) >= 2 and tickets[0].sent_date and tickets[1].sent_date:
            days_between = (tickets[1].sent_date - tickets[0].sent_date).days
        ws.cell(row=row_idx, column=col, value=days_between)

    # Ширина колонок
    widths = [15, 30, 15, 12, 15, 8, 40, 35, 12]
    for _ in range(5):
        widths += [15, 10, 40, 20, 15]
    widths += [15]

    for col, width in enumerate(widths, 1):
        letter = get_column_letter(col)
        ws.column_dimensions[letter].width = width

    # --- Отправка файла ---
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f"accounts_export_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.xlsx"

    log = Log(
        user_id=current_user.id,
        username=current_user.username,
        action="export_excel",
        target="",
        details=f"Выгружено: {len(accounts)}",
    )
    db.session.add(log)
    db.session.commit()

    return Response(
        buf.read(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )