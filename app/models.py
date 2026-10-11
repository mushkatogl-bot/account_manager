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
    reg_date = db.Column(db.Date, nullable=False)
    reg_time = db.Column(db.String(8), nullable=True)
    email = db.Column(db.String(255), nullable=False)
    email_password = db.Column(db.String(255), nullable=False)
    nick = db.Column(db.String(255), nullable=True)
    account_password = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(64), nullable=True)

    # --- Статус ---
    status = db.Column(db.String(32), default="online", nullable=False)

    # --- Куки ---
    cookies_text = db.Column(db.Text, nullable=True)

    # --- Support ---
    support_sent = db.Column(db.Boolean, default=False)
    support_status = db.Column(db.String(16), nullable=True)  # "pending" / "answered"
    support_text = db.Column(db.Text, nullable=True)

    # --- Продажа ---
    for_sale = db.Column(db.Boolean, default=False)
    sold = db.Column(db.Boolean, default=False)
    sold_date = db.Column(db.DateTime, nullable=True)
    sold_price = db.Column(db.Float, nullable=True)

    # --- Pending TOP ---
    pending_since = db.Column(db.DateTime, nullable=True)

    # --- Комментарий ---
    comment = db.Column(db.Text, nullable=True)

    # --- Служебное ---
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    creator = db.relationship("User", foreign_keys=[created_by], lazy=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # --- Связи ---
    unsubscribes = db.relationship("Unsubscribe", backref="account",
                                   cascade="all, delete-orphan", lazy=True)

    def __repr__(self):
        return f"<Account {self.email} [{self.status}]>"

    # ============================================================
    # ВКЛАДКИ
    # ============================================================
    @property
    def tab_category(self):
        """
        К какой вкладке относится аккаунт.
        Возвращает: 'for_sale', 'working', 'sold', 'invalid'
        """
        # Проданные — приоритет №1
        if self.sold or self.status == "SALE":
            return "sold"

        # Невалидные — приоритет №2
        if self.status in ("Anmelden", "ALL gesperrt"):
            return "invalid"

        # FOR SALE — Pending TOP и TOP online
        if self.status in ("Pending TOP", "TOP online"):
            return "for_sale"

        # Всё остальное — в работе (online, Gesperrt, unloc online)
        return "working"

    @property
    def is_for_sale_tab(self):
        return self.tab_category == "for_sale"

    @property
    def is_working_tab(self):
        return self.tab_category == "working"

    @property
    def is_sold_tab(self):
        return self.tab_category == "sold"

    @property
    def is_invalid_tab(self):
        return self.tab_category == "invalid"

    # ============================================================
    # ПОДСВЕТКА PENDING TOP (ОСТАВЬТЕ ОТЗЫВ)
    # ============================================================
    @property
    def needs_review(self):
        """
        True если:
        - статус Pending TOP
        - есть хотя бы одна отписка
        - с момента САМОЙ СВЕЖЕЙ отписки прошло ≥ 24 часа
        """
        if self.status != "Pending TOP":
            return False

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
    # ВСПОМОГАТЕЛЬНЫЕ СВОЙСТВА (для тултипа)
    # ============================================================
    @property
    def unsubs_count(self):
        return len(self.unsubscribes)

    @property
    def has_unsubs(self):
        return len(self.unsubscribes) > 0

    @property
    def support_status_display(self):
        if not self.support_sent and not self.support_status:
            return None
        if self.support_status == "pending":
            return "ожидание"
        if self.support_status == "answered":
            return "ответили"
        if self.support_sent:
            return "отправлено"


    @property
    def creator_username(self):
        """Имя пользователя, создавшего аккаунт"""
        return self.creator.username if self.creator else "—"

    return None


# ============================================================
# ОТПИСКИ
# ============================================================
class Unsubscribe(db.Model):
    __tablename__ = "unsubscribes"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    date = db.Column(db.Date, nullable=True)
    time = db.Column(db.String(8), nullable=True)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def datetime_full(self):
        """Дата + время отписки в виде datetime (UTC)"""
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
    username = db.Column(db.String(64), nullable=True)
    action = db.Column(db.String(64), nullable=False)
    target = db.Column(db.String(255), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Log {self.username} {self.action}>"