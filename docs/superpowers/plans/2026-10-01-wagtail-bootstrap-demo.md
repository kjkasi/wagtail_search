# Wagtail Bootstrap Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Создать воспроизводимое Wagtail LTS-демо с одной `HomePage`, дочерними страницами, Bootstrap navbar и Rich Text-контентом с изображениями и документами.

**Architecture:** Новый Django-проект использует приложение `home` с моделями `HomePage` и `ArticlePage`; навигация строится из опубликованных прямых дочерних страниц, отмеченных `Show in menus`. Rich Text Wagtail отвечает за текст, image chooser и document chooser, а Bootstrap 5.3.8 собирается через npm/esbuild в Django static.

**Tech Stack:** Python 3.10+, Django 5.2.x, Wagtail 7.4.3 LTS, SQLite, Bootstrap 5.3.8, Node.js/npm, esbuild, Django/Wagtail test runner.

**Spec:** `docs/superpowers/specs/2026-10-01-wagtail-bootstrap-demo-design.md`

## Global Constraints

- Использовать `wagtail==7.4.3` — актуальный LTS-релиз, установленный в ходе подготовки плана.
- Использовать совместимый диапазон `Django>=5.2,<5.3` и Python `>=3.10`.
- Использовать `bootstrap==5.3.8` через npm, без CDN.
- Использовать `esbuild` для сборки `frontend/main.js` в `static/site/main.css` и `static/site/main.js`.
- Контент дочерней страницы хранить в одном `RichTextField`; отдельные inline-панели галереи и документов не добавлять.
- Rich Text features: `h2`, `h3`, `bold`, `italic`, `ol`, `ul`, `link`, `document-link`, `image`.
- Навигация должна включать только прямых потомков `HomePage`, для которых одновременно выполняются `live()` и `in_menu()`.
- Команда `python manage.py seed_demo` должна быть идемпотентной и не перезаписывать изменённый пользователем `body`.
- Бинарные изображения и документы команда `seed_demo` не генерирует.

## Review Focus

- Страница с `Show in menus = false` не должна появляться в navbar — закрепить `test_nav_excludes_hidden_page` в Task 3.
- Непубликованная страница не должна быть доступна в публичной навигации — закрепить `test_nav_excludes_unpublished_page` в Task 3.
- Несколько изображений и документов в Rich Text должны преобразовываться в публичные `<img>` и document links — закрепить `test_article_renders_multiple_images_and_documents` в Task 3.
- Повторный `seed_demo` не должен дублировать страницы или затирать изменённый текст — закрепить `test_seed_demo_is_idempotent_and_preserves_body` в Task 5.
- Navbar должен использовать Bootstrap mobile toggler и собранный bundle — закрепить `test_base_template_contains_bootstrap_toggler_and_assets` в Task 3 и `npm run build` в Task 4.

---

### Task 1: Scaffold Wagtail project and runtime configuration

**Files:**
- Create: `requirements.txt`
- Create: `manage.py`
- Create: `config/__init__.py`
- Create: `config/settings.py`
- Create: `config/urls.py`
- Create: `config/wsgi.py`
- Create: `home/__init__.py`
- Create: `home/apps.py`
- Create: `home/models.py`
- Create: `home/migrations/__init__.py`
- Create: `home/tests/__init__.py`
- Create: `home/tests/test_project.py`
- Modify: `.gitignore`
- Create: `static/site/.gitkeep`

**Interfaces:**
- Produces Django settings module `config.settings` and Wagtail URL entrypoint `config.urls`.
- Produces installed Django app label `home`, used by all later tasks.

- [ ] **Step 1: Write the failing project smoke test**

Add `ProjectSmokeTests(SimpleTestCase)` with `test_wagtail_admin_login_is_available`, requesting `/admin/login/` and asserting HTTP 200.

- [ ] **Step 2: Run the smoke test to verify it fails**

Run: `python manage.py test home.tests.test_project -v 2`

Expected: FAIL because the project scaffold/settings do not exist yet.

- [ ] **Step 3: Scaffold the project and pin dependencies**

Create the Django/Wagtail project using the standard Wagtail project layout. Set `DJANGO_SETTINGS_MODULE=config.settings`, configure SQLite, templates, `STATIC_URL`, `STATIC_ROOT`, `STATICFILES_DIRS`, media settings, Wagtail middleware/context processors, `home.apps.HomeConfig`, `wagtail.images`, `wagtail.documents`, and the standard Wagtail admin/page/static URL routes. Put these exact runtime pins in `requirements.txt`:

```text
Django>=5.2,<5.3
wagtail==7.4.3
```

Keep generated secrets development-only and read `SECRET_KEY`/`DEBUG` from environment with safe local defaults. Add `static/site/main.css` and `static/site/main.js` to `.gitignore`; keep `static/site/.gitkeep` tracked.

- [ ] **Step 4: Run the smoke test and Django checks**

Run: `python manage.py test home.tests.test_project -v 2 && python manage.py check`

Expected: PASS and `System check identified no issues`.

- [ ] **Step 5: Commit the scaffold**

```bash
git add requirements.txt manage.py config home static/site/.gitkeep .gitignore
git commit -m "chore: scaffold wagtail project"
```

---

### Task 2: Implement page models and Rich Text configuration

**Files:**
- Modify: `home/models.py`
- Create: `home/migrations/0001_initial.py`
- Create: `home/tests/test_models.py`

**Interfaces:**
- Produces `BasePage(Page)`, `HomePage(BasePage)`, and `ArticlePage(BasePage)`.
- `HomePage` exposes `intro: RichTextField`, `max_count = 1`, and `subpage_types = ["home.ArticlePage"]`.
- `ArticlePage` exposes `body: RichTextField` and `parent_page_types = ["home.HomePage"]`.
- `BasePage.get_context(request, *args, **kwargs)` adds `navigation_items` to the template context.

- [ ] **Step 1: Write failing model tests**

Add tests with Wagtail `Page` tree fixtures:

```python
def test_home_page_allows_only_one_instance(self):
    self.assertEqual(HomePage.max_count, 1)

def test_article_page_is_only_allowed_below_home_page(self):
    self.assertEqual(HomePage.subpage_types, ["home.ArticlePage"])
    self.assertEqual(ArticlePage.parent_page_types, ["home.HomePage"])

def test_article_body_has_required_rich_text_features(self):
    self.assertEqual(
        ArticlePage._meta.get_field("body").features,
        ["h2", "h3", "bold", "italic", "ol", "ul", "link", "document-link", "image"],
    )
```

Also assert `BasePage.get_context()` returns only direct child pages that are live and in menu.

- [ ] **Step 2: Run model tests to verify they fail**

Run: `python manage.py test home.tests.test_models -v 2`

Expected: FAIL because the page classes and fields are not implemented.

- [ ] **Step 3: Implement `BasePage`, `HomePage`, and `ArticlePage` in `home/models.py`**

Use standard Wagtail `content_panels` with `FieldPanel("intro")` and `FieldPanel("body")`. Implement `get_context()` by obtaining the current site root and assigning `root_page.get_children().live().in_menu()` to `context["navigation_items"]`. Do not add custom StreamField blocks or inline media relations.

- [ ] **Step 4: Create migrations and run model tests**

Run:

```bash
python manage.py makemigrations home
python manage.py migrate
python manage.py test home.tests.test_models -v 2
```

Expected: migration succeeds and all model tests PASS.

- [ ] **Step 5: Commit the page model layer**

```bash
git add home/models.py home/migrations home/tests/test_models.py
git commit -m "feat: add wagtail home and article pages"
```

---

### Task 3: Build public templates, navbar, and Rich Text rendering

**Files:**
- Create: `home/templates/home/base.html`
- Create: `home/templates/home/home_page.html`
- Create: `home/templates/home/article_page.html`
- Create: `home/tests/test_pages.py`

**Interfaces:**
- Templates consume `page`, `navigation_items`, `intro`, and `body` from the Wagtail page context.
- `base.html` exposes `{% block title %}` and `{% block content %}` and loads `site/main.css` and `site/main.js`.

- [ ] **Step 1: Write failing page rendering tests**

Create a published `HomePage` with three `ArticlePage` children and test:

- `test_home_page_renders_nav_items`: response for `/` contains the visible child title and URL.
- `test_nav_excludes_hidden_page`: a live page with `show_in_menus=False` is absent from navbar.
- `test_nav_excludes_unpublished_page`: an unpublished page is absent from navbar.
- `test_article_renders_rich_text`: response contains article heading and rendered paragraph.
- `test_article_renders_multiple_images_and_documents`: create two Wagtail `Image` objects and two `Document` objects, store their chooser markup in `body`, request the article, and assert two image elements plus two document hrefs are present.
- `test_base_template_contains_bootstrap_toggler_and_assets`: response contains `navbar-toggler`, `data-bs-toggle="collapse"`, `{% static 'site/main.css' %}` output, and `{% static 'site/main.js' %}` output.

- [ ] **Step 2: Run page tests to verify they fail**

Run: `python manage.py test home.tests.test_pages -v 2`

Expected: FAIL because templates and page rendering are not implemented.

- [ ] **Step 3: Implement `base.html`**

Use a semantic Bootstrap 5 navbar with brand link to the current site root, a collapsed menu with `id="mainNavbar"`, `navbar-toggler`, `data-bs-toggle="collapse"`, and one link per `navigation_items`. Use `{% load static wagtailcore_tags %}` and render the child URLs with `{% pageurl item %}`.

- [ ] **Step 4: Implement `home_page.html` and `article_page.html`**

Extend `base.html`. Render `HomePage.intro` and child page cards/links on the home page. Render `ArticlePage.title` and `{{ page.body|richtext }}` on the article page. Keep media markup controlled by Wagtail’s Rich Text rewrite handlers; do not use `safe` on arbitrary fields.

- [ ] **Step 5: Run page tests to verify they pass**

Run: `python manage.py test home.tests.test_pages -v 2`

Expected: PASS, including hidden/unpublished navigation and multiple media assertions.

- [ ] **Step 6: Commit the public page layer**

```bash
git add home/templates home/tests/test_pages.py
git commit -m "feat: render bootstrap pages and navigation"
```

---

### Task 4: Add npm Bootstrap build pipeline

**Files:**
- Create: `package.json`
- Create: `package-lock.json`
- Create: `frontend/main.js`
- Create: `home/tests/test_assets.py`

**Interfaces:**
- Produces npm script `npm run build`.
- Produces generated files `static/site/main.css` and `static/site/main.js` consumed by `base.html`.

- [ ] **Step 1: Write the failing asset build test**

Add `AssetBuildTests.test_bootstrap_build_produces_css_and_js` in `home/tests/test_assets.py`; it must assert that `static/site/main.css` and `static/site/main.js` are non-empty, the CSS contains `.navbar`, and the JS contains Bootstrap collapse code.

- [ ] **Step 2: Run the asset test to verify it fails**

Run: `python manage.py test home.tests.test_assets -v 2`

Expected: FAIL because the generated assets do not exist.

- [ ] **Step 3: Implement `package.json` and `frontend/main.js`**

Set `bootstrap` to `5.3.8` and add `esbuild` as a dev dependency. Define `build` to bundle `frontend/main.js`, minify it, emit CSS beside the JS, and write both outputs to `static/site`. In `frontend/main.js`, import `bootstrap/dist/css/bootstrap.min.css` and `bootstrap/dist/js/bootstrap.bundle.js`.

- [ ] **Step 4: Install, build, and run the asset test**

Run:

```bash
npm install
npm run build
python manage.py test home.tests.test_assets -v 2
```

Expected: both generated files exist, are non-empty, the content assertions pass, and the build exits with code 0.

- [ ] **Step 5: Re-run the Django page suite with built assets**

Run: `python manage.py test home.tests.test_pages -v 2`

Expected: PASS with static references resolving under the configured development static setup.

- [ ] **Step 6: Commit the frontend pipeline**

```bash
git add package.json package-lock.json frontend/main.js home/tests/test_assets.py .gitignore
git commit -m "build: bundle bootstrap with esbuild"
```

---

### Task 5: Add idempotent demo data command

**Files:**
- Create: `home/management/__init__.py`
- Create: `home/management/commands/__init__.py`
- Create: `home/management/commands/seed_demo.py`
- Create: `home/tests/test_commands.py`

**Interfaces:**
- Provides `python manage.py seed_demo`.
- Uses stable slugs `demo-home`, `about`, `services`, and `contacts`.
- Creates/reuses one `HomePage` and three published `ArticlePage` objects, then points the default `Site.root_page` at the home page.

- [ ] **Step 1: Write failing command tests**

Add:

- `test_seed_demo_creates_home_and_three_articles`: call the command and assert one home page, three child pages, published state, stable slugs, and default site root.
- `test_seed_demo_is_idempotent_and_preserves_body`: call once, change an article body, call again, and assert page counts remain unchanged and the custom body remains unchanged.

- [ ] **Step 2: Run command tests to verify they fail**

Run: `python manage.py test home.tests.test_commands -v 2`

Expected: FAIL because `seed_demo` is not registered.

- [ ] **Step 3: Implement `Command.handle()` in `home/management/commands/seed_demo.py`**

Find or create the `HomePage` below the Wagtail root node using the stable slug. For each stable article slug, create it only when absent; publish newly created pages and leave an existing `body` unchanged when the page already exists. Use `Site.objects.get_or_create(is_default_site=True, defaults={...})` and assign `root_page=home_page`. Print a concise success summary suitable for README output.

- [ ] **Step 4: Run command tests to verify they pass**

Run: `python manage.py test home.tests.test_commands -v 2`

Expected: PASS, including the repeated-run preservation check.

- [ ] **Step 5: Run the command manually**

Run: `python manage.py seed_demo`

Expected: one home page and three article pages are created on first run; the second run reports reuse and creates no duplicates.

- [ ] **Step 6: Commit the demo data command**

```bash
git add home/management home/tests/test_commands.py
git commit -m "feat: add idempotent demo seed command"
```

---

### Task 6: Document local setup and perform full verification

**Files:**
- Modify: `README.md`
- Modify: `.gitignore` only if build/cache exclusions are missing

**Interfaces:**
- README provides the complete commands for Python setup, npm setup, migrations, superuser creation, demo seeding, and development server startup.
- The documented workflow produces the public site described in the spec without Python code edits.

- [ ] **Step 1: Write the setup checklist in README**

Document these exact commands for Windows PowerShell and a POSIX shell where syntax differs:

```bash
python -m venv .venv
# activate the virtualenv
python -m pip install -r requirements.txt
npm install
npm run build
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver
```

Document `/`, `/admin/`, how to edit a child page, how to insert multiple images with the image chooser, and how to insert multiple documents with the document chooser. State that media files are added through Wagtail admin and are not generated by `seed_demo`.

- [ ] **Step 2: Run the complete verification suite**

Run:

```bash
npm run build
python manage.py check
python manage.py test -v 2
python manage.py seed_demo
python manage.py seed_demo
git diff --check
git status --short
```

Expected: build, checks, all tests, and both seed runs succeed; `git diff --check` reports no whitespace errors; only intended source/documentation changes remain.

- [ ] **Step 3: Commit the documentation and final verification**

```bash
git add README.md .gitignore
git commit -m "docs: document wagtail demo setup"
```

- [ ] **Step 4: Report the final verification evidence**

Record the exact Wagtail/Django/Bootstrap versions, the successful test command, the successful npm build, and the manual URLs (`/` and `/admin/`) in the completion summary.
