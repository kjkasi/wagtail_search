# Wagtail Bootstrap Search Demo

Учебный сайт на Wagtail с редактируемыми секциями `foo`, `bar`, `baz`, RichText-статьями и autocomplete-поиском по страницам и связанным документам.

## Быстрый запуск

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
npm install
npm run build
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver
```

Откройте <http://127.0.0.1:8000/>. Секции и статьи редактируются через Wagtail admin по адресу `/admin/`.

`npm install` и `npm run build` нужны для первоначальной сборки локальных Bootstrap-файлов в `static/site/`. Во время запуска сайт использует только эти локальные CSS/JS-файлы и не загружает Bootstrap, шрифты или другие ресурсы с CDN и внешних origin.

## Контент и поиск

В `ArticlePage` можно использовать RichText, изображения и document links через стандартные Wagtail chooser'ы. Поиск ограничен опубликованными прямыми статьями секций текущего сайта и ищет заголовок, RichText, названия связанных документов и видимый текст их ссылок. Бинарное содержимое документов не индексируется.

Для повторного наполнения демо-данными выполните:

```bash
python manage.py seed_demo
```

Команда идемпотентна и не перезаписывает существующий текст статей.

## Проверки

```bash
python manage.py check
python manage.py test -v 2
npm run build
```
