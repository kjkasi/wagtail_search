# Wagtail Bootstrap Search Demo — Design Specification

## Goal

Создать новый с нуля учебный Wagtail-проект с редактируемыми пунктами navbar `foo`, `bar`, `baz`, дочерними RichText-страницами и autocomplete-поиском по их содержимому.

## Confirmed decisions

- Старый удалённый проект не восстанавливается; все файлы создаются заново.
- Используется Wagtail 7.4.3 LTS и совместимый Django 5.2.x.
- Для локальной разработки используется SQLite.
- Bootstrap работает без CDN и внешних запросов во время запуска: CSS и JS собираются локально в `static/`.
- Интернет/npm требуется только для первоначального `npm install` и сборки frontend.
- Поиск использует встроенный database backend Wagtail Search.
- `foo`, `bar`, `baz` — редактируемые Wagtail-страницы, а не строки, зашитые в шаблон.
- Каждая секция показывает только своих прямых опубликованных дочерних страниц.
- Поиск обрабатывает только прямых дочерних страниц секций текущего сайта.
- В поиск входят заголовок страницы, текст RichText, название документа и видимый текст ссылки на документ.

## Scope

### In scope

1. Новый Django/Wagtail-проект с приложением `home`.
2. Модельная структура `HomePage → SectionPage → ArticlePage`.
3. Bootstrap navbar с секциями и локальным autocomplete-поиском.
4. `ArticlePage` с одним RichText-полем, поддерживающим текст, изображения и ссылки на документы.
5. Рендеринг прямых дочерних страниц списком на странице каждой секции.
6. JSON endpoint `GET /search/?q=...`.
7. Поиск по страницам, названиям связанных документов и тексту document links.
8. Идемпотичная команда `python manage.py seed_demo`.
9. README с установкой, сборкой и запуском.
10. Автоматические Django/Wagtail-тесты моделей, страниц, поиска и seed-команды.

### Out of scope

- Elasticsearch/OpenSearch и отдельный поисковый сервис.
- Авторизация посетителей.
- Поиск по содержимому бинарных файлов документов.
- Поиск по тегам, категориям и изображениям.
- Вложенные секции и поиск на глубину более одного уровня.
- CDN Bootstrap и runtime-загрузка внешних ресурсов.
- Production deployment, Docker и CI.
- Отдельные gallery/document blocks вместо RichText.

## Architecture

### Page models

`home/models.py` содержит:

- `BasePage(Page)` — общий контекст с навигацией текущего Wagtail Site.
- `HomePage(BasePage)` — единственная корневая страница демо; разрешает только `SectionPage`.
- `SectionPage(BasePage)` — редактируемый пункт navbar; разрешает только `ArticlePage` и отображает прямых детей списком.
- `ArticlePage(BasePage)` — дочерняя страница с полем `body` типа `RichTextField`.

`ArticlePage.body` разрешает features:

- `h2`, `h3`;
- `bold`, `italic`;
- `ol`, `ul`;
- `link`;
- `image`;
- `document-link`.

`HomePage` и `SectionPage` используют ограничения `parent_page_types`/`subpage_types`, чтобы редактор не мог создать неправильную структуру.

### Navigation and templates

`BasePage.get_context()` добавляет в шаблоны прямых детей корня сайта, отфильтрованных по `live()` и `in_menu()`. Navbar выводит эти страницы как ссылки; названия `foo`, `bar`, `baz` приходят из Wagtail и могут быть изменены редактором.

Шаблоны:

- `home/templates/home/base.html` — HTML shell, локальные Bootstrap CSS/JS, navbar и search form/dropdown.
- `home/templates/home/home_page.html` — приветствие и список секций.
- `home/templates/home/section_page.html` — заголовок секции и список прямых дочерних статей.
- `home/templates/home/article_page.html` — заголовок и `body|richtext`.

RichText-rendering использует стандартные Wagtail image/document handlers, поэтому редактор может вставить несколько изображений и несколько ссылок на документы в одно поле.

### Search API

`home/views.py` предоставляет GET-only view `search(request)`, доступный по имени URL `page-search`.

Алгоритм:

1. Обрезать пробелы в `q`; пустой запрос возвращает `{"results": []}`.
2. Отклонять запрос длиннее 200 символов с HTTP 400.
3. Найти текущий `Site`; если сайт не найден, вернуть пустой результат.
4. Выбрать только опубликованные/public `ArticlePage`, являющиеся прямыми детьми опубликованных/public `SectionPage` текущего сайта.
5. Использовать Wagtail Search API по заголовку и `body` статьи.
6. Из RichText HTML выбранных статей извлечь document links: ID документа и видимый текст ссылки.
7. Среди документов, реально связанных с подходящими статьями, искать по `title` через Wagtail Search API; дополнительно считать совпадением видимый текст ссылки без учёта регистра.
8. Вернуть не более 10 результатов в порядке релевантности страниц, затем документов; каждый результат содержит `type`, `title`, `url`.

Документы без ссылки из подходящей дочерней страницы не попадают в результаты. Содержимое самих файлов не индексируется. URL страниц и документов формируются request-aware способом.

Endpoint не изменяет данные и не требует CSRF. Он использует только GET.

### Frontend search

`frontend/main.js` импортирует Bootstrap CSS и bundle JS, а также настраивает autocomplete:

- задержка запроса после ввода — 250 ms;
- предыдущий fetch отменяется через `AbortController`;
- устаревший ответ не заменяет результаты нового запроса;
- результаты показываются в Bootstrap-compatible dropdown/list group;
- пустой результат показывает `Ничего не найдено`;
- ошибка сети показывает `Не удалось выполнить поиск`;
- `Escape` и клик вне формы закрывают список;
- Arrow Up/Down позволяют перемещаться по результатам;
- текст выводится через `textContent`, а ссылки принимаются только с origin текущего сайта.

### Frontend assets

`package.json` содержит Bootstrap 5.3.x и esbuild. Команда `npm run build` собирает `frontend/main.js` в:

- `static/site/main.css`;
- `static/site/main.js`.

В runtime шаблон загружает только эти локальные файлы. CDN-ссылки и внешние шрифты не используются.

### Demo data

`home/management/commands/seed_demo.py`:

1. Находит стандартную корневую страницу Wagtail.
2. Создаёт или переиспользует `HomePage` с устойчивым slug.
3. Создаёт или переиспользует три `SectionPage` со slug/title `foo`, `bar`, `baz`.
4. Создаёт по одной демонстрационной `ArticlePage` под каждой секцией.
5. Публикует созданные страницы.
6. Настраивает default Site на `HomePage`.
7. При повторном запуске не создаёт дубликаты и не перезаписывает существующий body.

Команда не создаёт бинарные изображения и документы. README объясняет загрузку их через Wagtail admin и вставку в RichText.

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
  views.py
  management/commands/seed_demo.py
  templates/home/base.html
  templates/home/home_page.html
  templates/home/section_page.html
  templates/home/article_page.html
  tests/test_models.py
  tests/test_pages.py
  tests/test_search.py
  tests/test_commands.py
frontend/main.js
static/site/.gitkeep
manage.py
package.json
package-lock.json
requirements.txt
README.md
```

## Testing strategy

Django/Wagtail test runner должен проверить:

1. `HomePage` — единственная root demo page; ограничения родителей/детей корректны.
2. `SectionPage` допускается под `HomePage`, а `ArticlePage` — только под `SectionPage`.
3. Публичная страница секции показывает прямых опубликованных детей.
4. Страница, выключенная через `Show in menus`, не попадает в navbar.
5. Непубликованная или private страница не попадает в navbar и поиск.
6. RichText статьи отображает текст, несколько изображений и document links.
7. Поиск находит заголовок статьи и текст RichText.
8. Поиск находит title связанного документа и текст его RichText-ссылки.
9. Документ, не связанный с подходящей статьёй, не попадает в результаты.
10. Поиск ограничен текущим сайтом и прямыми детьми секций.
11. Пустой запрос, лимит длины 200 символов и максимум 10 результатов работают согласно API.
12. `seed_demo` создаёт структуру и безопасен при повторном запуске.
13. Base template подключает локальные `site/main.css` и `site/main.js`, без CDN URL.

Отдельный Jest/Node test setup не добавляется. Frontend проверяется ручным acceptance-сценарием после `npm run build`; серверная логика проверяется Django tests.

## Acceptance criteria

- После `migrate`, `npm install`, `npm run build`, `createsuperuser` и `seed_demo` проект запускается без ручного редактирования Python-кода.
- В navbar отображаются редактируемые секции `foo`, `bar`, `baz`.
- Каждая секция отображает список своих прямых дочерних страниц.
- Редактор может вставить в одну статью несколько изображений и несколько документов через штатные Wagtail chooser'ы.
- RichText корректно отображается на публичной странице.
- При наборе текста autocomplete показывает релевантные страницы и документы без перезагрузки.
- Поиск работает без внешних запросов и индексирует заголовки, RichText, названия документов и видимый текст document links.
- Публичные, site-scoped и direct-child ограничения соблюдаются.
- Повторный запуск `seed_demo` не создаёт дубликаты и не уничтожает редакторский контент.
- README содержит команды локального запуска и поясняет, что npm нужен только для первоначальной сборки локальных Bootstrap assets.

## Risks and mitigations

- **RichText document links хранятся как HTML:** использовать безопасный HTML parser, валидировать numeric document IDs и обрабатывать отсутствующие/удалённые документы без 500.
- **Поиск может смешать страницы разных сайтов:** явно ограничивать queryset `descendant_of(site.root_page)` и проверять прямого родителя `SectionPage`.
- **Скрытые или неопубликованные данные могут утечь через autocomplete:** применять `live()`, `public()` и `in_menu()` отдельно для соответствующего поведения и покрыть это тестами.
- **Bootstrap может случайно вернуться к CDN:** проверять шаблон и README на отсутствие внешних asset URL; build должен производить локальные файлы.
- **Повторный seed может перезаписать ручные изменения:** искать страницы по стабильному slug и изменять body только при создании.
