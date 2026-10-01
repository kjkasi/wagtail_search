# Wagtail Bootstrap Demo

Минимальный учебный сайт на Wagtail LTS: одна главная страница, дочерние страницы, Bootstrap navbar и Rich Text-контент с изображениями и документами.

## Требования

- Python 3.10+
- Node.js и npm
- Wagtail 7.4.3 LTS
- Django 5.2.x

## Установка

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install
npm run build
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver
```

### macOS/Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
npm install
npm run build
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver
```

После запуска:

- публичный сайт: http://127.0.0.1:8000/
- Wagtail admin: http://127.0.0.1:8000/admin/

`npm run build` собирает Bootstrap 5.3.8 в `static/site/main.css` и `static/site/main.js`. Эти файлы не хранятся в Git и пересобираются после `npm install`.

## Наполнение сайта

Команда `python manage.py seed_demo` создаёт или переиспользует:

- главную страницу `Wagtail Bootstrap Demo` со slug `demo-home`;
- дочерние страницы `about`, `services` и `contacts`.

Команду можно запускать повторно: она не создаёт дубликаты и не перезаписывает изменённый редактором `body`.

Чтобы добавить контент:

1. Откройте `/admin/` и войдите созданным суперпользователем.
2. В разделе **Pages** откройте одну из дочерних страниц.
3. Напишите текст в Rich Text editor.
4. Для нескольких фотографий используйте кнопку изображения и выберите файлы из Wagtail Images.
5. Для нескольких документов используйте кнопку ссылки на документ и выберите файлы из Wagtail Documents.
6. Сохраните и опубликуйте страницу.
7. Убедитесь, что **Show in menus** включён, если страница должна быть в navbar.

Изображения отображаются непосредственно в тексте, документы становятся ссылками для скачивания. `seed_demo` не создаёт бинарные медиафайлы — они загружаются через Wagtail admin.

## Проверка

```bash
npm run build
python manage.py check
python manage.py test -v 2
python manage.py seed_demo
python manage.py seed_demo
git diff --check
```
