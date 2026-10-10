from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash

from app import db, login_manager
from app.models import User, Log

bp = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            log = Log(
                user_id=user.id,
                username=user.username,
                action="login_success",
                target=request.remote_addr,
                details=(request.headers.get("User-Agent") or "")[:250],
            )
            db.session.add(log)
            db.session.commit()
            return redirect(url_for("routes.index"))

        # Неудачная попытка
        log = Log(
            user_id=None,
            username=username or "—",
            action="login_failed",
            target=request.remote_addr,
            details=(request.headers.get("User-Agent") or "")[:250],
        )
        db.session.add(log)
        db.session.commit()
        flash("Неверный логин или пароль")

    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    log = Log(
        user_id=current_user.id,
        username=current_user.username,
        action="logout",
        target=request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()

    logout_user()
    return redirect(url_for("auth.login"))