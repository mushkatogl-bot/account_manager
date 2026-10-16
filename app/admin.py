from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from app import db
from app.models import User, Log

bp = Blueprint("admin", __name__, url_prefix="/admin")


# ============================================================
# ДЕКОРАТОР: только админ
# ============================================================
def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != "admin":
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return wrapper


# ============================================================
# СПИСОК ПОЛЬЗОВАТЕЛЕЙ
# ============================================================
@bp.route("/")
@admin_required
def index():
    users = User.query.order_by(User.id.asc()).all()
    return render_template("admin.html", users=users)


# ============================================================
# СОЗДАНИЕ ПОЛЬЗОВАТЕЛЯ
# ============================================================
@bp.route("/users/add", methods=["POST"])
@admin_required
def user_add():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    role = request.form.get("role", "user")

    if not username or not password:
        flash("Логин и пароль обязательны", "danger")
        return redirect(url_for("admin.index"))

    if User.query.filter_by(username=username).first():
        flash(f"Пользователь {username} уже существует", "warning")
        return redirect(url_for("admin.index"))

    u = User(
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
    )
    db.session.add(u)
    db.session.commit()

    log = Log(
        user_id=current_user.id,
        username=current_user.username,
        action="admin_create_user",
        target=username,
        details=f"Роль: {role}",
    )
    db.session.add(log)
    db.session.commit()

    flash(f"Пользователь {username} создан", "success")
    return redirect(url_for("admin.index"))


# ============================================================
# СМЕНА ПАРОЛЯ
# ============================================================
@bp.route("/users/<int:user_id>/password", methods=["POST"])
@admin_required
def user_change_password(user_id):
    u = User.query.get_or_404(user_id)
    new_password = request.form.get("password", "").strip()

    if not new_password:
        flash("Пароль не может быть пустым", "danger")
        return redirect(url_for("admin.index"))

    u.password_hash = generate_password_hash(new_password)
    db.session.commit()

    log = Log(
        user_id=current_user.id,
        username=current_user.username,
        action="admin_change_password",
        target=u.username,
        details="",
    )
    db.session.add(log)
    db.session.commit()

    flash(f"Пароль пользователя {u.username} изменён", "success")
    return redirect(url_for("admin.index"))


# ============================================================
# УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ
# ============================================================
@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def user_delete(user_id):
    u = User.query.get_or_404(user_id)

    if u.id == current_user.id:
        flash("Нельзя удалить самого себя", "danger")
        return redirect(url_for("admin.index"))

    if u.username == "admin":
        flash("Нельзя удалить главного админа", "danger")
        return redirect(url_for("admin.index"))

    username = u.username
    db.session.delete(u)
    db.session.commit()

    log = Log(
        user_id=current_user.id,
        username=current_user.username,
        action="admin_delete_user",
        target=username,
        details="",
    )
    db.session.add(log)
    db.session.commit()

    flash(f"Пользователь {username} удалён", "warning")
    return redirect(url_for("admin.index"))
# ============================================================
# СМЕНА ПРАВ ПОЛЬЗОВАТЕЛЯ
# ============================================================
@bp.route("/users/<int:user_id>/permissions", methods=["POST"])
@admin_required
def user_permissions(user_id):
    u = User.query.get_or_404(user_id)

    if u.role == "admin":
        flash("У админа всегда полные права", "warning")
        return redirect(url_for("admin.index"))

    u.can_view_others = request.form.get("can_view_others") == "on"
    u.can_edit_others = request.form.get("can_edit_others") == "on"
    db.session.commit()

    log = Log(
        user_id=current_user.id,
        username=current_user.username,
        action="admin_change_permissions",
        target=u.username,
        details=f"view={u.can_view_others}, edit={u.can_edit_others}",
    )
    db.session.add(log)
    db.session.commit()

    flash(f"Права {u.username} обновлены", "success")
    return redirect(url_for("admin.index"))
