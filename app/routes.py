from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from datetime import datetime

from app.models import Account, Log, Unsubscribe
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
    user_filter = request.args.get("user_filter", "").strip()  # id юзера или пусто

    # --- Базовый запрос ---
    query = Account.query

    # --- Права доступа ---
    is_admin = (current_user.role == "admin")
    can_view_others = is_admin or current_user.can_view_others
    can_edit_others = is_admin or current_user.can_edit_others

    # Если не может видеть чужие — только свои
    if not can_view_others:
        query = query.filter(Account.created_by == current_user.id)
    elif user_filter:
        # Фильтр по конкретному юзеру
        if user_filter == "mine":
            query = query.filter(Account.created_by == current_user.id)
        else:
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

    # --- Сортировка ---
    if sort_by == "status":
        query = query.order_by(Account.status.asc())
    else:
        query = query.order_by(Account.reg_date.desc())

    all_accounts = query.all()

    # --- Разбиваем на 4 вкладки ---
    for_sale = [a for a in all_accounts if a.is_for_sale_tab]
    working  = [a for a in all_accounts if a.is_working_tab]
    sold     = [a for a in all_accounts if a.is_sold_tab]
    invalid  = [a for a in all_accounts if a.is_invalid_tab]

    # --- Список юзеров для фильтра (только если может видеть чужие) ---
    users_for_filter = []
    if can_view_others:
        from app.models import User
        users_for_filter = User.query.order_by(User.username.asc()).all()

    return render_template(
        "index.html",
        tab=tab,
        q=q,
        sort_by=sort_by,
        user_filter=user_filter,
        users_for_filter=users_for_filter,
        can_view_others=can_view_others,
        can_edit_others=can_edit_others,
        for_sale=for_sale,
        working=working,
        sold=sold,
        invalid=invalid,
        for_sale_count=len(for_sale),
        working_count=len(working),
        sold_count=len(sold),
        invalid_count=len(invalid),
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
    cost_amount = float(cost_str) if cost_str else None

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

    if status == "SALE":
        a.sold = True
        a.sold_date = datetime.utcnow()
    if status == "Pending TOP":
        a.pending_since = datetime.utcnow()

    db.session.add(a)
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
    return redirect(url_for("routes.index"))


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
        "for_sale": a.for_sale,
        "sold": a.sold,
        "sold_price": a.sold_price or "",
        "sold_date": a.sold_date.strftime("%Y-%m-%d %H:%M") if a.sold_date else "",
        "has_cookies": bool(a.cookies_text),
        "cookies_text": a.cookies_text or "",
        "support_sent": a.support_sent,
        "support_status": a.support_status or "",
        "support_text": a.support_text or "",
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
    a.cost_amount = float(cost_str) if cost_str else None

    # --- Продажа ---
    a.for_sale = request.form.get("for_sale") == "on"
    price_str = request.form.get("sold_price", "").strip()
    a.sold_price = float(price_str) if price_str else None

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

    # --- Support ---
    a.support_sent = request.form.get("support_sent") == "on"
    a.support_status = request.form.get("support_status") or None
    a.support_text = request.form.get("support_text", "").strip() or None

    # --- Куки ---
    if "cookies_text" in request.form:
        cookies = request.form["cookies_text"].strip()
        a.cookies_text = cookies if cookies else None

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
    return redirect(url_for("routes.index"))


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