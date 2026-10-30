# DiLS — логистическая система

Веб-сервис для управления рейсами и заявками.
Python · Django 5 · Bootstrap 5 · SQLite/PostgreSQL.

---

## Роли

| Роль | Что делает | Куда попадает после входа |
|------|------------|---------------------------|
| **Менеджер** | Создаёт заявки, заполняет свою часть рейса | `/trips/` |
| **Логист** | Заполняет данные логиста: ТК, водитель, машина, цена, ТТН | `/requests/` |
| **Администратор** | Управление пользователями и справочниками | `/settings/` |

---

## Быстрый старт (Windows)

Открыть PowerShell:

```powershell
cd C:\Users\Alex\Desktop\Rufus\project_DiLS\dils_project

# 1. Активировать venv (если он есть)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Создать .env из шаблона
copy .env.example .env

# 4. Применить миграции
python manage.py makemigrations core
python manage.py migrate

# 5. Заполнить демо-данными (опционально)
python manage.py seed_data

# 6. Запустить
python manage.py runserver
```

Открыть в браузере: <http://127.0.0.1:8000/>

---

## Демо-доступы

После `python manage.py seed_data` создаются пользователи:

| Логин | Пароль | Роль |
|-------|--------|------|
| `admin` | `dils12345` | Администратор (superuser) |
| `manager` | `dils12345` | Менеджер |
| `logist` | `dils12345` | Логист |

⚠️ **Обязательно** смените пароли перед использованием в реальной работе.

---

## Быстрый старт (Linux / macOS)

```bash
cd dils_project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py makemigrations core
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

---

## Переменные окружения (`.env`)

Создайте `.env` в корне проекта (рядом с `manage.py`):

```env
DJANGO_SECRET_KEY=<сгенерировать>
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# SQLite (по умолчанию)
DB_ENGINE=sqlite

# PostgreSQL — раскомментировать и заполнить
# DB_ENGINE=postgres
# DB_NAME=dils
# DB_USER=dils
# DB_PASSWORD=secret
# DB_HOST=127.0.0.1
# DB_PORT=5432
```

**Как получить `DJANGO_SECRET_KEY`:**

```powershell
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Скопировать вывод и вставить в `.env` вместо `<сгенерировать>`.

---

## Структура проекта

```
dils_project/
├── config/                  # настройки Django
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── core/                    # основное приложение
│   ├── models.py            # роли, справочники, рейсы, история
│   ├── admin.py             # регистрация в админке
│   ├── forms.py             # формы рейсов, справочников
│   ├── views.py             # 18 view-функций
│   ├── urls.py
│   ├── signals.py           # логирование изменений
│   ├── middleware.py        # текущий пользователь в thread-local
│   ├── context_processors.py
│   ├── utils.py             # фильтры, дашборды, парсинг
│   ├── templatetags/
│   │   └── dils_tags.py
│   ├── services/
│   │   ├── trip_service.py
│   │   └── report_service.py
│   ├── management/commands/
│   │   └── seed_data.py
├── templates/               # HTML-шаблоны
├── static/                  # CSS/JS
├── media/                   # загружаемые файлы (сейчас пусто)
└── manage.py
```

---

## Что уже работает

- 🔐 Логин / логаут, разделение по ролям
- 🚛 **Рейсы** (менеджер): список, создание, редактирование, история
- 📋 **Заявки** (логист): список, редактирование данных логиста
- 🔔 Уведомление о новых заявках
- 📊 **Отчёты**: суммы нал/безнал, итог, doughnut-график
- 👤 **Профиль** + справочники (заказчики / ТК)
- ⚙ **Настройки** (только админ): пользователи
- 🧩 Фильтры и дашборды — настраиваются per-user (сохраняются в БД)
- 📝 История изменений полей рейса
- 🚗 Автоформат гос. номера: `м362еа790` → `М 362 АЕ 790`
- 📚 Справочники: заказчики, ТК, водители, машины, марки, типы оплаты

---

## Что в работе / следующие итерации

- 🧾 Парсер «Информация по доставке» (regex/NLP-разбор текста в структурированные поля)
- 📱 Мобильное меню (offcanvas)
- 🔁 Импорт/экспорт в Excel
- 🧪 Тесты — будут написаны после завершения основной функциональности

---

## Управление через Django Admin

Полный доступ к моделям: <http://127.0.0.1:8000/admin/>

Логин `admin` / `dils12345` (после `seed_data`).

---

## Полезные команды

```powershell
# Новая миграция после правок моделей
python manage.py makemigrations

# Применить миграции
python manage.py migrate

# Открыть оболочку Django
python manage.py shell

# Создать суперюзера вручную
python manage.py createsuperuser

# Пересоздать БД с нуля (осторожно — удалит все данные!)
del db.sqlite3
python manage.py migrate
python manage.py seed_data
```

---

## Лицензия

Внутренний проект. Все права у владельца.