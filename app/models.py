from app import db
from flask_login import UserMixin
from datetime import datetime


# ============================================================
# ПОЛЬЗОВАТЕЛИ
# ============================================================
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(16), default="user")  # "user" или "admin"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================================
# АККАУНТЫ
# ============================================================
class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)

    # --- Основное ---
    reg_date = db.Column(db.Date, nullable=False)            # дата регистрации (обязательно)
    reg_time = db.Column(db.String(8), nullable=True)        # время "12:30" (не обязательно)
    email = db.Column(db.String(255), nullable=False)        # почта
    email_password = db.Column(db.String(255), nullable=False)  # пароль от почты
    nick = db.Column(db.String(255), nullable=True)          # ник аккаунта
    account_password = db.Column(db.String(255), nullable=False)  # пароль от аккаунта
    phone = db.Column(db.String(64), nullable=True)          # телефон

    # --- Статус ---
    # Возможные: Gesperrt, online, TOP online, unloc online, Pending TOP,
    #            Anmelden, ALL gesperrt, SALE
    status = db.Column(db.String(32), default="online", nullable=False)

    # --- Куки (храним текстом) ---
    cookies_text = db.Column(db.Text, nullable=True)

    # --- Support ---
    support_sent = db.Column(db.Boolean, default=False)      # письмо отправлено
    support_status = db.Column(db.String(16), nullable=True)  # "pending" / "answered" / None
    support_text = db.Column(db.Text, nullable=True)         # текст письма

    # --- Продажа ---
    for_sale = db.Column(db.Boolean, default=False)          # выставлен на продажу
    sold = db.Column(db.Boolean, default=False)              # продан
    sold_date = db.Column(db.DateTime, nullable=True)        # дата продажи
    sold_price = db.Column(db.Float, nullable=True)          # цена

    # --- Pending TOP ---
    pending_since = db.Column(db.DateTime, nullable=True)    # когда поставили Pending TOP

    # --- Комментарий (общий) ---
    comment = db.Column(db.Text, nullable=True)

    # --- Служебное ---
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- Связи ---
    unsubscribes = db.relationship("Unsubscribe", backref="account",
                                   cascade="all, delete-orphan", lazy=True)

    def __repr__(self):
        return f"<Account {self.email} [{self.status}]>"

    # Удобные свойства для шаблонов
    @property
    def is_invalid(self):
        """Попадает ли во вкладку НЕВАЛИД/ПРОДАНЫ"""
        return self.status in ("Anmelden", "ALL gesperrt", "SALE") or self.sold

    @property
    def is_working(self):
        """Попадает ли во вкладку В РАБОТЕ"""
        return not self.is_invalid

    @property
    def needs_review(self):
        """С момента последней отписки прошло ≥24ч, а статус всё ещё Pending TOP"""
        if self.status != "Pending TOP":
            return False

        # Ищем самую свежую отписку
        if not self.unsubscribes:
            return False

        latest = None
        for u in self.unsubscribes:
            dt = u.datetime_full
            if dt and (latest is None or dt > latest):
                latest = dt

        if latest is None:
            return False

        delta = datetime.utcnow() - latest
        return delta.total_seconds() >= 24 * 3600


# ============================================================
# ОТПИСКИ
# ============================================================
class Unsubscribe(db.Model):
    __tablename__ = "unsubscribes"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    date = db.Column(db.Date, nullable=True)      # дата отписки
    time = db.Column(db.String(8), nullable=True) # время "22:30"
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def datetime_full(self):
        """Дата + время отписки в виде datetime"""
        if not self.date:
            return None
        if self.time:
            try:
                h, m = self.time.split(":")
                return datetime(self.date.year, self.date.month, self.date.day,
                                int(h), int(m))
            except (ValueError, AttributeError):
                pass
        return datetime(self.date.year, self.date.month, self.date.day)


# ============================================================
# ЛОГИ
# ============================================================
class Log(db.Model):
    __tablename__ = "logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    username = db.Column(db.String(64), nullable=True)       # на случай, если юзера удалят
    action = db.Column(db.String(64), nullable=False)        # "login", "create_account", ...
    target = db.Column(db.String(255), nullable=True)        # id/email объекта
    details = db.Column(db.Text, nullable=True)              # подробности
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Log {self.username} {self.action}>"