from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # проверяем, нет ли уже такого юзера
    existing = User.query.filter_by(username="admin").first()
    if existing:
        print("Админ уже существует")
    else:
        u = User(
            username="admin",
            password_hash=generate_password_hash("admin123"),
            role="admin",
        )
        db.session.add(u)
        db.session.commit()
        print("Админ создан: логин=admin, пароль=admin123")