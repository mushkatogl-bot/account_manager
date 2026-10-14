from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Пожалуйста, войдите, чтобы получить доступ."

    from app import routes, auth, admin, accounting
    app.register_blueprint(auth.bp)
    app.register_blueprint(routes.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(accounting.bp)

    with app.app_context():
        db.create_all()

        # ==================================================
        # ВРЕМЕННО: автосоздание двух пользователей
        # После первого деплоя — УБРАТЬ этот блок!
        # ==================================================
        from app.models import User
        from werkzeug.security import generate_password_hash

        users_to_create = [
            {"username": "admin", "password": "Pass79461355!", "role": "admin"},
            {"username": "MAX",   "password": "Mn558899",      "role": "user"},
        ]

        for u in users_to_create:
            existing = User.query.filter_by(username=u["username"]).first()
            if not existing:
                new_user = User(
                    username=u["username"],
                    password_hash=generate_password_hash(u["password"]),
                    role=u["role"],
                )
                db.session.add(new_user)
                print(f"✅ Создан пользователь: {u['username']} ({u['role']})")
            else:
                print(f"ℹ️ Пользователь {u['username']} уже существует")

        db.session.commit()
        # ==================================================
        # КОНЕЦ временного блока
        # ==================================================

    return app