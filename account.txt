📘 Account Manager — шпаргалка проекта
🎯 Что это
Веб-приложение для ведения учёта игровых/почтовых аккаунтов, которые продаются в интернете. Каждый аккаунт имеет свой статус, куки, письма в поддержку, отписки и историю продажи. Есть бухгалтерия (расходы/доходы/прибыль) и логи всех действий.

Разработано: февраль 2026, стек — Flask + SQLAlchemy + Bootstrap 5.

Стек:

Python 3.11 + Flask

Flask-SQLAlchemy (ORM)

Flask-Login (авторизация)

SQLite (локально) / PostgreSQL (Render)

Jinja2 (шаблоны)

Bootstrap 5.3 (UI)

Gunicorn (боевой сервер)

GitHub + Render (деплой)

📁 Структура папок
text
account_manager/
│
├── app/                              # основной пакет приложения
│   ├── __init__.py                   # создание Flask-приложения
│   ├── models.py                     # модели БД (User, Account, Unsubscribe, Log, Expense)
│   ├── routes.py                     # роуты главной страницы (аккаунты, куки, отписки)
│   ├── auth.py                       # логин/логаут
│   ├── admin.py                      # админ-панель (управление юзерами и правами)
│   ├── accounting.py                 # бухгалтерия (расходы/доходы/прибыль)
│   ├── logs_utils.py                 # хелперы для логов (можно не использовать)
│   │
│   ├── static/
│   │   └── style.css                 # доп. стили (тёмная тема, тултип, пульсация)
│   │
│   └── templates/
│       ├── base.html                 # базовый шаблон (navbar + flash-сообщения + тёмная тема)
│       ├── login.html                # страница входа
│       ├── index.html                # главная (таблица аккаунтов, 4 вкладки, модалки)
│       ├── logs.html                 # страница логов
│       ├── admin.html                # админ-панель
│       └── accounting.html           # бухгалтерия
│
├── instance/
│   └── app.db                        # SQLite база (локально, не в git)
│
├── venv/                             # виртуальное окружение Python (не в git)
│
├── config.py                         # конфиг (SECRET_KEY, DATABASE_URL)
├── run.py                            # точка входа локально
├── create_admin.py                   # скрипт создания первых юзеров
├── seed.py                           # скрипт добавления тестовых аккаунтов
├── main.py                           # старый файл (не используется, можно удалить)
│
├── requirements.txt                  # список зависимостей
├── Procfile                          # команда запуска для Render
├── .gitignore                        # что НЕ заливать в git
├── README.md                         # этот файл
│
└── .git/                             # git-репозиторий
🔑 Роли и права
Роль	Права
admin	Видит всё: любые аккаунты, все расходы, может редактировать/удалять чужие, управляет юзерами и правами
user	Видит только свои аккаунты. Если админ дал галочки — видит и/или редактирует чужие
Галочки в админке (для не-админов):

☑ Видеть чужие аккаунты — can_view_others

☑ Редактировать чужие — can_edit_others

Удалять чужие может только админ (или если у юзера обе галочки).

📊 Модель данных
User
id, username, password_hash, role

can_view_others, can_edit_others — галочки прав

created_at

Account
Основное: reg_date, reg_time, email, email_password, nick, account_password, phone

Статус: status (см. ниже)

Куки: cookies_text (хранится как текст в БД)

Support: support_sent, support_status (pending / answered), support_text

Продажа: for_sale, sold, sold_date, sold_price

Бухгалтерия: cost_amount (стоимость номера, если NULL → $2 по умолчанию)

Pending TOP: pending_since (автоматически при смене статуса)

Прочее: comment, created_by (FK на User), creator (relationship), created_at, updated_at

Связь: unsubscribes (одна ко многим)

Unsubscribe
account_id (FK), email, date, time, comment, created_at

Log
user_id, username, action, target, details, created_at

Expense (бухгалтерия)
date, category (email / proxy / other), amount (в $), comment, created_by, created_at

🏷️ Статусы аккаунта
Статус	Вкладка	Бейдж	Описание
online	🟢 В РАБОТЕ	зелёный	Всё хорошо
Gesperrt	🟢 В РАБОТЕ	красный	Заблокирован, ждём разблокировки
unloc online	🟢 В РАБОТЕ	синий	После ответа поддержки
online Loshung	🟢 В РАБОТЕ	бирюзовый	Объявления не выставляются, ждём ТП
Pending TOP	🟣 FOR SALE	жёлтый	Ждём TOP-плашку
TOP online	🟣 FOR SALE	светло-фиолетовый	Топовый аккаунт
SALE	💚 ПРОДАНЫ	фиолетовый	Продан
Anmelden	🔴 НЕВАЛИД	серый	Невалидный
ALL gesperrt	🔴 НЕВАЛИД	тёмно-красный	Полностью заблокирован
Автологика:

SALE → sold=True, sold_date=now

Pending TOP → pending_since=now

🗂 Четыре вкладки на главной
🟣 FOR SALE — Pending TOP, TOP online (готовые к продаже)

🟢 В РАБОТЕ — online, Gesperrt, unloc online, online Loshung

💚 ПРОДАНЫ — SALE (проданные)

🔴 НЕВАЛИД — Anmelden, ALL gesperrt

🔔 Подсветка «ОСТАВЬТЕ ОТЗЫВ»
Логика:

Статус Pending TOP

Есть хотя бы одна отписка

С момента самой свежей отписки прошло ≥24 часа

Тогда:

Строка подсвечивается жёлтым

Появляется пульсирующий бейдж ⚠️ ОСТАВЬТЕ ОТЗЫВ

🖥 Страницы и роуты
URL	Что	Кто видит
/login	Вход	Все
/	Главная (таблица аккаунтов)	Авторизованные
/account/add	POST: добавить	Авторизованные
/account/<id>/json	GET: JSON для модалки	Авторизованные (с проверкой прав)
/account/<id>/edit	POST: сохранить	Авторизованные (с проверкой прав)
/account/<id>/delete	POST: удалить	Владелец или админ
/account/<id>/cookies/download	GET: скачать .txt	Авторизованные
/account/<id>/cookies/delete	POST: удалить куки	Авторизованные
/account/<id>/unsubs/json	GET: отписки	Авторизованные
/account/<id>/unsubs/add	POST: добавить отписку	Авторизованные
/unsubs/<id>/delete	POST: удалить отписку	Авторизованные
/logs	Логи (все действия)	Все авторизованные
/admin/	Админ-панель	Только админ
/accounting	Бухгалтерия	Все авторизованные (каждый видит только своё)
/expenses/add	POST: добавить расход	Авторизованные
/expenses/<id>/edit	POST: редактировать расход	Владелец
/expenses/<id>/delete	POST: удалить расход	Владелец
/logout	Выход	Авторизованные
💰 Бухгалтерия
Считаем в долларах, время по МСК (UTC+3).

Автоматически:
🎮 Номера: effective_cost × кол-во аккаунтов (cost_amount, если задано, иначе $2)

💰 Доход: сумма sold_price проданных аккаунтов

Вручную (Expense):
📧 Почты (пачки)

🌐 Прокси

📦 Прочее (подписки и т.д.)

Метрики:
Расходы = Номера + Почты + Прокси + Прочее

Прибыль = Доход − Расходы

Маржа = (Прибыль / Доход) × 100%

Показывается:
За всё время (4 карточки)

За конкретный месяц (выпадающий список)

Разбивка расходов по категориям

Вкладка По месяцам — все месяцы с цифрами

Вкладка Расходы — список + редактирование + удаление

Вкладка Доходы — автоматически из проданных (⚠️ если нет sold_price)

Удалённые аккаунты
Не считаются в бухгалтерии — удаление жёсткое (DELETE FROM accounts).

📎 Куки
Хранятся в БД (поле cookies_text, тип TEXT)

Заливаются вручную (текстом через модалку)

Скачиваются как .txt с шапкой:

text
log:pass
mail:pass

email_аккаунта:пароль_аккаунта
email_аккаунта:пароль_почты

{здесь сами куки}
Имя файла: {email}_{пароль_почты}_{дата_регистрации}.txt

Удаление — только через confirm с CAPS-текстом

📨 Отписки
Можно несколько на один аккаунт

Поля: email собеседника, дата, время, комментарий

Используются для подсчёта «ОСТАВЬТЕ ОТЗЫВ» (24 часа от последней отписки)

Добавляются/удаляются через AJAX (без перезагрузки страницы)

🛠 Support
Чекбокс: «Письмо отправлено»

Статус: pending (ожидание) / answered (ответили)

Текст письма — многострочное поле

Автоподсказка: при выборе answered → предлагает сменить статус на unloc online или ALL gesperrt

👤 Тултип (клик по ℹ️)
Статичный popup рядом с кнопкой ℹ️. Показывает:

🔑 Пароль от аккаунта + кнопка копирования 📋

📝 Комментарий

🍪 Куки: есть/нет + кнопка ⬇ Скачать

🛠 Support: отправлено / ожидание / ответили / —

💰 Продажа: на продажу за 
X
/
проданза
X/проданзаX / —

📨 Отписка: есть (N) / нет

Закрывается по клику вне или по кнопке ℹ️ снова.

📜 Логи
Логируются все важные действия:

Вход, создание/редактирование/удаление аккаунта

Смена статуса, продажа

Скачивание / удаление куки

Добавление / удаление отписки

Добавление / редактирование / удаление расхода

Действия админа (создание/удаление юзера, смена пароля, смена прав)

Показываются на /logs с фильтрами по юзеру и типу действия. Доступно всем.

🌗 Тёмная тема
Переключатель 🌙 / ☀️ в navbar

Выбор сохраняется в localStorage

Применяется через атрибут data-bs-theme на <html>

Скрипт в <head> применяет тему до отрисовки (не мигает белым)

🚀 Локальный запуск
bash
cd C:\Users\Admin\Desktop\account_manager
venv\Scripts\activate
python run.py
Открыть: http://127.0.0.1:5000

Логины:

admin / Pass79461355!

MAX / Mn558899

Если что-то сломалось — пересоздать БД:

bash
del instance\app.db
python create_admin.py
python run.py
☁️ Деплой на Render
Ссылка: https://account-manager-ht9e.onrender.com

GitHub: https://github.com/mushkatogl-bot/account_manager

PostgreSQL: account-manager-db (Frankfurt)

Environment Variables в Render:

DATABASE_URL — Internal Database URL

PYTHON_VERSION — 3.11.5

Build Command: pip install -r requirements.txt
Start Command: gunicorn run:app

Деплой:

bash
git add .
git commit -m "описание изменений"
git push
Render пересоберёт автоматически через 2-3 минуты.

⚠️ Важно знать
1. SQLAlchemy не меняет существующие таблицы
Когда добавляешь новое поле в модель — на боевой БД оно не появится автоматически. Нужен SQL через Render Shell:

bash
python -c "
from app import create_app, db
from sqlalchemy import text
app = create_app()
with app.app_context():
    with db.engine.connect() as conn:
        conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS field_name TYPE'))
        conn.commit()
    print('✅ Готово')
"
2. Render Free засыпает
Первый заход после 15 минут простоя — 30-60 секунд на пробуждение.

3. Бесплатная PostgreSQL удаляется через 30 дней
Если БД на Free-плане — она удалится. Либо переводи на платный (~$7/мес), либо делай бэкапы через External URL + DBeaver.

4. Бэкапы БД
Раз в неделю:

Render → БД → Connections → External Database URL

Открой DBeaver (бесплатный), подключись

Инструменты → Бэкап → сохрани .sql на компьютер

5. venv/ и instance/ не в git
Проверь .gitignore:

text
venv/
__pycache__/
*.pyc
instance/
.idea/
*.db
.env
🎯 Ключевые решения (почему так)
Что	Почему
Куки в БД, не в файлах	Все юзеры могут читать/писать без работы с файлами. Мелкие размеры (100 КБ) — ок для БД
Всё в долларах	Проще считать, курс не нужен
МСК (UTC+3)	Чтобы «октябрь» совпадал с твоим календарём
Каждый видит свою бухгалтерию	Админ смотрит чужую через логин/пароль
Удаление жёсткое	Удалённые аккаунты не считаются в расходах
Expenses — отдельная таблица	Гибко: почты/прокси/прочее — всё вручную
Пароли хешированы	werkzeug.security.generate_password_hash
Права через галочки	can_view_others, can_edit_others
Тултип по клику, не по hover	Тултип не убегает от курсора
🆘 Если что-то сломалось
Логи локально — смотри в терминале, где запущен python run.py

Логи Render — Web Service → Logs (последние 30 строк)

Логи БД — БД → Logs (если проблема с подключением)

DevTools браузера — F12 → Console (JS-ошибки) и Network (запросы)

Частые ошибки:

column X does not exist → нужен ALTER TABLE через Shell

ModuleNotFoundError → проверь requirements.txt и pip install -r requirements.txt

TemplateNotFound → проверь, что шаблон лежит в app/templates/

gunicorn: command not found → gunicorn должен быть в requirements.txt

Could not connect to server → проверь DATABASE_URL в Environment

📌 Что ещё можно добавить
📥 Экспорт аккаунтов в Excel/CSV

💾 Кнопка «Скачать БД» в админке

🔔 Уведомления о просроченных Pending TOP

📱 Мобильная адаптация

🔐 Двухфакторка для админа

📊 Дашборд со статистикой по месяцам

🎨 Настраиваемые категории расходов

🌐 Деплой на VPS (если Render перестанет устраивать)

Конец шпаргалки. Удачи! 🍀

Сохрани этот файл как README.md в корне проекта — он не потеряется даже если чат удалится.