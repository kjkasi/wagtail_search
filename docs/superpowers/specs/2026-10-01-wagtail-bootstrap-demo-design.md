# Wagtail Bootstrap Demo — Design Specification

## Goal

Создать воспроизводимый учебный Wagtail-проект с одной главной страницей, несколькими дочерними страницами, Bootstrap-навигацией и редактируемым Rich Text-контентом, в который редактор может вставлять несколько изображений и ссылок на несколько документов.

## Confirmed decisions

- Используется актуальный Wagtail LTS на момент реализации; точная версия фиксируется в `requirements.txt`.
- Bootstrap подключается через npm, а не через CDN.
- Для сборки frontend используется `esbuild`.
- Контент дочерней страницы хранится в одном `RichTextField`.
- Изображения выбираются через Wagtail image chooser и вставляются в Rich Text.
- Документы выбираются через Wagtail document chooser и вставляются в Rich Text как ссылки.
- Отдельные inline-панели галереи и документов не входят в демо.
- Навигация строится из прямых дочерних страниц `HomePage`, опубликованных и отмеченных `Show in menus`.

## Scope

### In scope

1. Новый Django/Wagtail проект с приложением `home`.
2. Модели `HomePage` и `ArticlePage` с ограничением дерева страниц.
3. Bootstrap 5.x CSS и JavaScript, собранные из npm-зависимостей.
4. Адаптивный базовый шаблон с Bootstrap navbar и мобильным toggler.
5. Главная страница со вступлением и ссылками на дочерние страницы.
6. Страница статьи с заголовком и Rich Text-контентом.
7. Идемпотичная команда `python manage.py seed_demo`.
8. README с установкой, сборкой, созданием пользователя, наполнением медиа и запуском.
9. Автоматические тесты моделей, публичных страниц, navbar и seed-команды.

### Out of scope

- Авторизация посетителей.
- Поиск, категории, теги и pagination.
- Отдельная галерея с lightbox.
- Отдельный список документов под статьёй.
- Хранение медиа вне штатной Wagtail library.
- Production deployment, Docker и CI.
- Кастомизация Wagtail admin beyond page models and Rich Text features.

## Architecture

### Python application

`home/models.py` содержит:

- `BasePage(Page)` — общий `get_context()`; добавляет в шаблон `navigation_items` из прямых дочерних страниц корневой страницы сайта, отфильтрованных по `live()` и `in_menu()`.
- `HomePage(BasePage)` — единственная главная страница (`max_count = 1`), поле `intro` типа `RichTextField`, разрешает только `ArticlePage`.
- `ArticlePage(BasePage)` — поле `body` типа `RichTextField`, разрешён только как прямой потомок `HomePage`.

`body` включает ровно следующие Rich Text features:

- `h2`
- `h3`
- `bold`
- `italic`
- `ol`
- `ul`
- `link`
- `document-link`
- `image`

Классы страниц используют стандартные `content_panels` Wagtail и `FieldPanel` для `intro`/`body`. Сложные кастомные block types не добавляются.

### URL and templates

`config/urls.py` подключает:

- Wagtail admin по `/admin/`;
- Wagtail documents/images/media routes;
- Wagtail page serving;
- Django static files в development.

Шаблоны приложения:

- `home/templates/home/base.html` — HTML5 shell, Bootstrap navbar, ссылки на static CSS/JS, блоки `title` и `content`.
- `home/templates/home/home_page.html` — вступление и Bootstrap cards/links для дочерних страниц.
- `home/templates/home/article_page.html` — заголовок и `body|richtext`.

Navbar использует `navigation_items`, поэтому скрытые через `Show in menus` страницы не появляются, а unpublished pages не видны посетителям.

### Frontend assets

`package.json` фиксирует:

- `bootstrap` версии 5.x;
- `esbuild` версии, совместимой с поддерживаемым Node.js.

`frontend/main.js` импортирует `bootstrap/dist/css/bootstrap.min.css` и `bootstrap/dist/js/bootstrap.bundle.js`. Скрипт `npm run build` собирает `frontend/main.js` в:

- `static/site/main.css`;
- `static/site/main.js`.

Bootstrap bundle используется для мобильного navbar toggler; отдельный Popper dependency не добавляется, так как он входит в bundle.

### Demo data

Команда `home/management/commands/seed_demo.py`:

1. Находит единственный корневой Wagtail node.
2. Создаёт или переиспользует одну `HomePage`.
3. Создаёт или переиспользует три `ArticlePage` с демонстрационными русскоязычными заголовками и Rich Text-текстом.
4. Публикует страницы.
5. Обновляет default `Site`, чтобы его `root_page` указывал на `HomePage`.
6. Не создаёт дубликаты при повторном запуске.

Команда не генерирует бинарные изображения и документы. README объясняет: загрузить их в Wagtail admin, открыть любую дочернюю страницу и вставить нужное количество изображений/ссылок на документы через Rich Text toolbar.

## Testing strategy

Используется Django/Wagtail test runner.

Проверки должны покрывать:

1. `HomePage` нельзя создать более одного раза через модельное ограничение.
2. `ArticlePage` разрешён под `HomePage`, а другие типы родителей не разрешены.
3. Публичный ответ главной страницы содержит дочерние страницы с `show_in_menus=True`.
4. Страница с `show_in_menus=False` не попадает в navbar.
5. Непубликованная дочерняя страница не попадает в публичный navbar.
6. Публичный ответ статьи содержит заголовок и отрендеренный Rich Text.
7. `seed_demo` создаёт ожидаемую структуру и безопасен при повторном запуске.
8. Базовый шаблон подключает `site/main.css` и `site/main.js`.

Отдельные браузерные тесты не требуются; Bootstrap layout проверяется шаблонными assertions и ручным запуском development server.

## Acceptance criteria

- После `migrate`, `npm install`, `npm run build`, `createsuperuser` и `seed_demo` сайт запускается без ручного редактирования Python-кода.
- На `/` отображается Bootstrap navbar с дочерними страницами и содержимое `HomePage`.
- Каждая дочерняя страница доступна из navbar и отображает Rich Text.
- Редактор может вставить в одну дочернюю страницу несколько изображений и несколько документов через Wagtail chooser.
- Вставленные изображения отображаются в тексте, а документы доступны как ссылки для скачивания.
- Мобильный navbar раскрывается средствами Bootstrap bundle.
- Повторный запуск `seed_demo` не создаёт дубликаты.
- README содержит все команды для локального запуска.

## File layout

```text
config/
  __init__.py
  settings.py
  urls.py
  wsgi.py
home/
  __init__.py
  apps.py
  models.py
  admin.py
  management/commands/seed_demo.py
  templates/home/base.html
  templates/home/home_page.html
  templates/home/article_page.html
  tests/test_models.py
  tests/test_pages.py
  tests/test_commands.py
frontend/main.js
static/site/.gitkeep
manage.py
package.json
package-lock.json
requirements.txt
README.md
```

## Risks and mitigations

- **Изменение актуального LTS к моменту реализации:** версия Wagtail определяется до создания `requirements.txt` и фиксируется exact pin вместе с совместимой Django-версией.
- **Rich Text chooser зависит от Wagtail feature names:** тесты проверяют итоговую конфигурацию поля и публичный рендеринг, а реализация использует штатные features `image` и `document-link`.
- **npm-сборка не выполнена:** README явно отделяет `npm install` и `npm run build`; тесты Django запускаются после наличия собранных static-файлов.
- **Повторный seed после ручного изменения контента:** команда ищет страницы по стабильным slug и не перезаписывает существующий пользовательский body.
