# Wagtail Bootstrap Search Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Создать с нуля учебный Wagtail-сайт с редактируемыми секциями `foo`, `bar`, `baz`, RichText-статьями, локальным Bootstrap navbar и autocomplete-поиском по страницам и связанным документам.

**Architecture:** Дерево страниц будет `HomePage → SectionPage → ArticlePage`. Wagtail database search будет искать заголовок и RichText статьи, а отдельный безопасный parser извлечёт связанные document links для поиска названий документов и видимого текста ссылок. Bootstrap 5.3 CSS/JS будет собираться esbuild в локальные static-файлы; runtime не использует CDN.

**Tech Stack:** Python 3.10+, Django 5.2.x, Wagtail 7.4.3 LTS, SQLite, Bootstrap 5.3.8, esbuild, Django/Wagtail test runner.

**Spec:** `docs/superpowers/specs/2026-10-08-wagtail-bootstrap-search-demo-design.md`

## Global Constraints

- «Старый удалённый проект не восстанавливается; все файлы создаются заново.»
- «Используется Wagtail 7.4.3 LTS и совместимый Django 5.2.x.»
- «Bootstrap работает без CDN и внешних запросов во время запуска: CSS и JS собираются локально в `static/`.»
- «Интернет/npm требуется только для первоначального `npm install` и сборки frontend.»
- «Поиск использует встроенный database backend Wagtail Search.»
- «Каждая секция показывает только своих прямых опубликованных дочерних страниц.»
- «Поиск обрабатывает только прямых дочерних страниц секций текущего сайта.»
- «В поиск входят заголовок страницы, текст RichText, название документа и видимый текст ссылки на документ.»
- Не добавлять Elasticsearch/OpenSearch, вложенные секции, поиск по бинарному содержимому файлов, CDN, Docker или production deployment.

## Review Focus

- **Malformed/stale document links:** RichText с нечисловым, отсутствующим или удалённым document ID не должен давать HTTP 500 и не должен возвращать чужой документ; закрепить в Task 5 тестом `test_search_ignores_invalid_and_missing_document_links`.
- **Visibility and site boundaries:** unpublished/private страницы и документы другого Wagtail Site не должны появляться в navbar или autocomplete; закрепить в Tasks 3 и 5 тестами `test_private_or_unpublished_children_are_hidden` и `test_search_is_scoped_to_current_site`.
- **Direct-child boundary:** вложенная статья второго уровня не должна считаться дочерней статьёй секции; закрепить в Task 5 тестом `test_search_ignores_nested_articles`.
- **Input limits and result bounds:** пробелы, пустой запрос, 201 символ и более 10 совпадений должны обрабатываться точно по API; закрепить в Task 5 тестами `test_empty_query_returns_no_results`, `test_long_query_returns_400` и `test_search_returns_at_most_10_results`.
- **Frontend race/XSS behavior:** устаревший fetch не должен перезаписывать новые результаты, а title/URL API не должны вставляться как HTML или переходить на чужой origin; закрепить в Task 6 ручным acceptance-сценарием с быстрым изменением запроса и вредным значением результата.

---

### Task 1: Scaffold Django/Wagtail project and local frontend build

**Files:**
- Create: `requirements.txt`
- Create: `manage.py`
- Create: `config/__init__.py`
- Create: `config/settings.py`
- Create: `config/urls.py`
- Create: `config/wsgi.py`
- Create: `home/__init__.py`
- Create: `home/apps.py`
- Create: `home/views.py`
- Create: `home/tests/__init__.py`
- Create: `package.json`
- Create: `frontend/main.js`
- Create: `static/site/.gitkeep`
- Create: `.gitignore`
- Test: `home/tests/test_project.py`

**Interfaces:**
- Produces Django settings module `config.settings`, WSGI application `config.wsgi.application`, app config `home.apps.HomeConfig`, and npm command `npm run build`.
- Produces local build targets `static/site/main.css` and `static/site/main.js`.
- Produces temporary `search(request: HttpRequest) -> JsonResponse` returning `{"results": []}` at named route `page-search`; Task 5 replaces this stub with the real search implementation.

- [ ] **Step 1: Write the failing project smoke test**

Create `home/tests/test_project.py` with tests that assert Django can load the project and that `settings.INSTALLED_APPS` contains `home`, `wagtail`, and `wagtail.admin`, while `STATIC_URL` and `MEDIA_URL` are configured.

- [ ] **Step 2: Run the smoke test to verify the scaffold is absent**

Run: `python manage.py test home.tests.test_project -v 2`

Expected: FAIL because `manage.py` and `config.settings` do not exist yet.

- [ ] **Step 3: Implement the Django/Wagtail scaffold**

Add `Django>=5.2,<5.3` and `wagtail==7.4.3` to `requirements.txt`. Configure SQLite, Wagtail core/admin/documents/images apps, `home`, templates, static/media paths, middleware, and a development-safe secret key in `config/settings.py`; configure Wagtail admin, documents, page serving, and the temporary `path("search/", search, name="page-search")` route in `config/urls.py`. Add the temporary empty JSON `search` view in `home/views.py` so templates can reverse the route before Task 5.

Add `package.json` with `bootstrap` `5.3.8`, esbuild, and the script `"build": "esbuild frontend/main.js --bundle --minify --outdir=static/site"`. Import `bootstrap/dist/css/bootstrap.min.css` and `bootstrap/dist/js/bootstrap.bundle.js` from `frontend/main.js`. Ignore `static/site/*.css` and `static/site/*.js` while keeping `static/site/.gitkeep`; do not add CDN URLs.

- [ ] **Step 4: Run project and asset verification**

Run:

```bash
python -m pip install -r requirements.txt
python manage.py check
npm install
npm run build
```

Expected: Django reports no system-check errors; esbuild creates `static/site/main.css` and `static/site/main.js`.

- [ ] **Step 5: Run the smoke test to verify it passes**

Run: `python manage.py test home.tests.test_project -v 2`

Expected: PASS.

- [ ] **Step 6: Commit the scaffold**

```bash
git add .gitignore requirements.txt manage.py config home package.json package-lock.json frontend/main.js static/site
git commit -m "chore: scaffold wagtail bootstrap project"
```

### Task 2: Add the page model tree and migrations

**Files:**
- Create: `home/models.py`
- Create: `home/migrations/__init__.py`
- Create: `home/migrations/0001_initial.py`
- Create: `home/tests/test_models.py`

**Interfaces:**
- Produces `BasePage(Page)`, `HomePage(BasePage)`, `SectionPage(BasePage)`, and `ArticlePage(BasePage)`.
- `HomePage.max_count == 1` and `HomePage.subpage_types == ["home.SectionPage"]`.
- `SectionPage.parent_page_types == ["home.HomePage"]` and `SectionPage.subpage_types == ["home.ArticlePage"]`.
- `ArticlePage.parent_page_types == ["home.SectionPage"]` and `ArticlePage.body` is a `RichTextField` with features `h2`, `h3`, `bold`, `italic`, `ol`, `ul`, `link`, `image`, and `document-link`.
- `BasePage.get_context(request, *args, **kwargs) -> dict` adds `navigation_items` containing direct live/public/in-menu children of the current site root.

- [ ] **Step 1: Write failing model tests**

Add tests named `test_home_page_allows_only_one_instance`, `test_page_type_relationships_are_restricted`, and `test_article_body_has_required_rich_text_features`. Assert the exact parent/subpage type lists, `max_count`, and feature set.

- [ ] **Step 2: Run the model tests to verify they fail**

Run: `python manage.py test home.tests.test_models -v 2`

Expected: FAIL because the page classes and migration do not exist.

- [ ] **Step 3: Implement the page models**

Define the four page classes in `home/models.py`. Use Wagtail `FieldPanel` for `ArticlePage.body`; keep `HomePage` and `SectionPage` without extra content fields. Implement `BasePage.get_context()` with the current `Site.find_for_request(request)` and a fallback to the page root, then query only direct root children with `live()`, `public()`, and `in_menu()`.

- [ ] **Step 4: Generate and apply the migration**

Run:

```bash
python manage.py makemigrations home
python manage.py migrate
```

Expected: migration `home/migrations/0001_initial.py` is created and all migrations apply successfully.

- [ ] **Step 5: Run the model tests to verify they pass**

Run: `python manage.py test home.tests.test_models -v 2`

Expected: PASS.

- [ ] **Step 6: Commit the page model layer**

```bash
git add home/models.py home/migrations home/tests/test_models.py
git commit -m "feat: add wagtail demo page models"
```

### Task 3: Render navigation, sections, and RichText pages

**Files:**
- Create: `home/templates/home/base.html`
- Create: `home/templates/home/home_page.html`
- Create: `home/templates/home/section_page.html`
- Create: `home/templates/home/article_page.html`
- Create: `home/tests/test_pages.py`

**Interfaces:**
- `base.html` exposes `#pageSearchForm`, `#pageSearchInput`, and `#pageSearchResults` for Task 6; its form action resolves the `page-search` route scaffolded in Task 1.
- `HomePage` renders its direct live/public sections through the existing `navigation_items` context.
- `SectionPage.get_context()` exposes `children` containing only direct live/public child pages.
- Public page responses load only `/static/site/main.css` and `/static/site/main.js` for Bootstrap assets.

- [ ] **Step 1: Write failing page-rendering tests**

Create Wagtail client tests named `test_home_shows_visible_sections_in_navbar`, `test_hidden_or_unpublished_section_is_not_in_navbar`, `test_section_lists_only_direct_published_articles`, `test_article_renders_rich_text`, and `test_base_template_uses_local_bootstrap_assets`. Assert visible section links, absence of `show_in_menus=False` and unpublished sections, absence of nested/unpublished article links from the section list, rendered body text, and absence of `https://cdn`/`http://cdn` asset references.

- [ ] **Step 2: Run the page tests to verify they fail**

Run: `python manage.py test home.tests.test_pages -v 2`

Expected: FAIL because the page templates and section context do not exist.

- [ ] **Step 3: Implement the page contexts and templates**

Add `SectionPage.get_context()` using direct children only and create the four templates. Use Bootstrap navbar classes with a mobile toggler, render `navigation_items` as editable links, render section children as a list/cards, and render article content with `{{ page.body|richtext }}`. Load `{% static 'site/main.css' %}` and `{% static 'site/main.js' %}` only; include the search form IDs required by Task 6.

- [ ] **Step 4: Wire Wagtail page serving and apply migrations**

Ensure `config/urls.py` includes Wagtail page serving and run `python manage.py migrate`.

- [ ] **Step 5: Run page tests to verify they pass**

Run: `python manage.py test home.tests.test_pages -v 2`

Expected: PASS.

- [ ] **Step 6: Commit the public page layer**

```bash
git add home/templates home/tests/test_pages.py home/models.py
git commit -m "feat: render bootstrap navigation and rich text pages"
```

### Task 4: Add idempotent demo data seeding

**Files:**
- Create: `home/management/__init__.py`
- Create: `home/management/commands/__init__.py`
- Create: `home/management/commands/seed_demo.py`
- Create: `home/tests/test_commands.py`

**Interfaces:**
- Produces management command `python manage.py seed_demo`.
- The command creates/reuses one `HomePage` with stable slug, three `SectionPage` records with slug/title `foo`, `bar`, `baz`, and one sample `ArticlePage` below each.
- Re-running the command preserves existing article `body` values and creates no duplicate pages.

- [ ] **Step 1: Write failing command tests**

Create `test_seed_demo_creates_expected_tree` and `test_seed_demo_is_idempotent_and_preserves_body`. Assert the exact section slugs, one article per initial section, published state, default Site root, unchanged page counts after the second run, and preservation of a manually changed body.

- [ ] **Step 2: Run the command tests to verify they fail**

Run: `python manage.py test home.tests.test_commands -v 2`

Expected: FAIL because `seed_demo` does not exist.

- [ ] **Step 3: Implement `Command.handle(*args, **options) -> None`**

Find the Wagtail root page, create/reuse the stable demo pages by parent and slug, set sample body only on newly created articles, publish created/updated demo pages, and point the default `Site` to `HomePage`. Do not create image/document binaries.

- [ ] **Step 4: Run command tests to verify they pass**

Run: `python manage.py test home.tests.test_commands -v 2`

Expected: PASS.

- [ ] **Step 5: Manually run the command twice**

Run:

```bash
python manage.py seed_demo
python manage.py seed_demo
```

Expected: both runs complete without errors and the second run reports/reuses existing pages without duplicates.

- [ ] **Step 6: Commit seed support**

```bash
git add home/management home/tests/test_commands.py
git commit -m "feat: add idempotent demo seed command"
```

### Task 5: Implement site-scoped page and document search

**Files:**
- Create: `home/tests/test_search.py`
- Modify: `home/views.py`
- Modify: `home/models.py`

**Interfaces:**
- `MAX_SEARCH_QUERY_LENGTH: int = 200`.
- `MAX_SEARCH_RESULTS: int = 10`.
- `DOCUMENT_BATCH_SIZE: int = 100` for bounded document-ID queries.
- `_DocumentLinkParser.links: list[tuple[str, str]]` extracts `(document_id, visible_link_text)` from Wagtail document anchors.
- `_document_links_for_pages(pages: Iterable[Page]) -> Iterator[tuple[str, str]]` parses RichText fields from the supplied pages.
- `_documents_for_ids_in_order(document_ids: Iterable[str], limit: int) -> list[Document]` returns existing documents in link order without unbounded `pk__in` parameters.
- `search(request: HttpRequest) -> JsonResponse` serves `GET /search/?q=...` and returns `{"results": [{"type": str, "title": str, "url": str}]}` or HTTP 400 with `{"error": "query_too_long", "results": []}`.
- `ArticlePage.search_fields` includes the inherited title search field and `SearchField("body")`.

- [ ] **Step 1: Write failing parser and endpoint tests**

Add tests named `test_search_finds_article_title_and_rich_text`, `test_search_finds_linked_document_title`, `test_search_finds_document_link_text`, `test_search_ignores_invalid_and_missing_document_links`, `test_search_excludes_unlinked_document`, `test_search_is_scoped_to_current_site`, `test_search_ignores_nested_articles`, `test_empty_query_returns_no_results`, `test_long_query_returns_400`, and `test_search_returns_at_most_10_results`.

Use real Wagtail `Document` instances with `SimpleUploadedFile` and RichText HTML containing normal, nested, invalid, missing, and repeated document anchors. Assert page/document result `type`, title and URL; assert no 500 and no unrelated document leakage; assert only live/public direct articles under sections of the current Site are eligible; assert whitespace is stripped, 201 characters returns 400, and 10 is the hard result cap.

- [ ] **Step 2: Run search tests to verify they fail**

Run: `python manage.py test home.tests.test_search -v 2`

Expected: FAIL because the scaffold view always returns an empty result and `body` is not yet a Wagtail search field.

- [ ] **Step 3: Add the article search field**

Update `ArticlePage.search_fields` to append `SearchField("body")` to the inherited page search fields, preserving title indexing.

- [ ] **Step 4: Implement document-link extraction**

Implement `_DocumentLinkParser` with `html.parser.HTMLParser`, accepting only anchors with `linktype="document"` and ASCII decimal IDs, collecting visible text across nested markup, normalizing whitespace, and skipping malformed links. Implement `_document_links_for_pages()` by inspecting RichTextField values on each specific page.

- [ ] **Step 5: Implement bounded document lookup and the search view**

In `search()`, scope candidate pages to the current Site, live/public `SectionPage`s and their direct live/public `ArticlePage` children. Search title/body with Wagtail Search API. Parse links only from eligible pages, search linked document titles with Wagtail Search API, add case-insensitive visible-link matches, preserve relevance/order, and return at most 10 page/document results. Use request-aware URLs and ignore missing documents.

- [ ] **Step 6: Replace the scaffold view and run search tests**

Replace the Task 1 empty JSON implementation while preserving the existing `page-search` route before the Wagtail catch-all route. Run:

```bash
python manage.py test home.tests.test_search -v 2
```

Expected: PASS.

- [ ] **Step 7: Commit search support**

```bash
git add home/views.py home/models.py home/tests/test_search.py config/urls.py
git commit -m "feat: add scoped rich text and document search"
```

### Task 6: Add local Bootstrap autocomplete behavior and usage documentation

**Files:**
- Modify: `frontend/main.js`
- Modify: `home/templates/home/base.html`
- Create: `README.md`
- Modify: `.gitignore`

**Interfaces:**
- Produces `setupPageSearch()`, called once from `frontend/main.js`.
- Uses the existing DOM IDs `pageSearchForm`, `pageSearchInput`, and `pageSearchResults`.
- Calls the form action with `GET` parameter `q`, debounced by 250 ms, and renders API result objects `{type, title, url}` without `innerHTML`.
- Keeps runtime assets local; generated files remain build outputs and are not CDN dependencies.

- [ ] **Step 1: Add the frontend acceptance fixture and template contract**

Update `base.html` with an accessible search form, `aria-expanded`, result container, and Bootstrap-compatible positioning. Add the README command sequence and explain that `npm install`/`npm run build` are only needed to produce local assets, while runtime makes no external requests.

- [ ] **Step 2: Implement `setupPageSearch()`**

Add 250 ms debounce, `AbortController` cancellation, request sequence protection, loading/empty/error messages, safe same-origin URL validation, `textContent` title rendering, Escape/outside-click closing, and Arrow Up/Down navigation. Keep the existing Bootstrap import and call `setupPageSearch()` after definition.

- [ ] **Step 3: Build the local assets**

Run: `npm run build`

Expected: `static/site/main.css` and `static/site/main.js` are generated and contain the bundled local Bootstrap assets; no template references a CDN.

- [ ] **Step 4: Run the complete automated suite**

Run:

```bash
python manage.py check
python manage.py test -v 2
npm run build
python manage.py seed_demo
```

Expected: all Django tests pass, the system check is clean, frontend build succeeds, and seed completes without errors.

- [ ] **Step 5: Perform manual acceptance testing**

Run `python manage.py runserver`, open `/`, and verify: navbar shows `foo`, `bar`, `baz`; each section lists direct articles; Wagtail RichText images and document links render; typing finds page body terms, document titles and visible link text; changing the query quickly shows only current results; Escape/outside click closes the list; mobile navbar toggles; browser network panel shows no CDN or external Bootstrap request.

- [ ] **Step 6: Commit frontend and documentation**

```bash
git add frontend/main.js home/templates/home/base.html README.md .gitignore
git commit -m "feat: add offline bootstrap autocomplete search"
```

### Task 7: Final verification and review handoff

**Files:**
- Modify only files required by verification fixes.
- Test: full repository test suite and frontend build.

**Interfaces:**
- Final branch must contain the approved spec, implementation plan, all project files, and passing verification commands.

- [ ] **Step 1: Check the complete diff and repository state**

Run:

```bash
git status --short
git diff --check
git diff --cached --check
```

Expected: no whitespace errors; only intended project/spec/plan files are present. Generated `static/site/main.css` and `static/site/main.js` remain ignored build outputs.

- [ ] **Step 2: Run final verification**

Run:

```bash
python manage.py check
python manage.py test -v 2
npm run build
```

Expected: all commands exit with status 0.

- [ ] **Step 3: Review acceptance criteria against the running demo**

Confirm every criterion in the spec is demonstrated by an automated test or the manual acceptance sequence in Task 6; fix any failing criterion before claiming completion.

- [ ] **Step 4: Commit only verified fixes**

```bash
git add <verified changed files>
git commit -m "test: verify wagtail bootstrap search demo"
```
