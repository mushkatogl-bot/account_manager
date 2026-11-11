from app import create_app, db
from app.models import Account, SupportTicket

app = create_app()

with app.app_context():
    accounts = Account.query.all()
    migrated = 0

    for a in accounts:
        # Если уже есть тикеты — пропускаем
        if a.support_tickets:
            continue

        # Если у аккаунта были старые данные о письме
        if a.support_text or a.support_date:
            outcome = "pending"
            if a.is_unlocked:
                outcome = "unlocked"
            elif a.is_all_gesperrt:
                outcome = "all_gesperrt"

            t = SupportTicket(
                account_id=a.id,
                letter_number=1,
                sent_date=a.support_date or a.reg_date,
                text=a.support_text,
                screens_sent=a.screens_sent or False,
                outcome=outcome,
                resolved_date=a.support_action_date,
            )
            db.session.add(t)

            # Очищаем старые поля
            a.support_date = None
            a.support_text = None
            a.support_action_date = None
            a.is_unlocked = False
            a.is_all_gesperrt = False
            a.screens_sent = False

            migrated += 1

    db.session.commit()
    print(f"✅ Миграция завершена. Создано тикетов: {migrated}")