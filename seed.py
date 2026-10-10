from app import create_app, db
from app.models import Account
from datetime import date

app = create_app()

with app.app_context():
    a = Account(
        reg_date=date(2026, 1, 15),
        reg_time="12:30",
        email="test1@mail.com",
        email_password="pass123",
        nick="PlayerOne",
        account_password="accpass1",
        status="online",
    )
    db.session.add(a)
    db.session.commit()
    print("Добавлен 1 аккаунт")