# Поиск по заголовкам страниц Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить в navbar динамический autocomplete-поиск по заголовкам опубликованных страниц текущего Wagtail-сайта с результатами в выпадающем списке.

**Architecture:** Django view `search(request)` отдаёт JSON по `GET /search/?q=...`, используя Wagtail Search API для live-потомков текущего Site и ограничивая ответ 10 результатами. Базовый шаблон содержит доступную форму и контейнер dropdown, а `frontend/main.js` с debounce запрашивает JSON, безопасно строит ссылки и защищается от устаревших ответов.

**Tech Stack:** Python 3.10+, Django 5.2.x, Wagtail 7.4.3, Django/Wagtail test runner, Bootstrap 5.3.8, esbuild, browser Fetch API.

**Spec:** `docs/superpowers/specs/2026-10-01-page-title-search-design.md`

## Global Constraints

- Backend endpoint: `GET /search/?q=<query>`.
- Для поиска используется Wagtail Search API, а не отдельный `title__icontains`-запрос.
- Ищутся все опубликованные страницы текущего сайта, включая страницы с `show_in_menus=False`.
- Корневая `HomePage` текущего сайта не показывается в результатах.
- В выпадающем списке показывается не более 10 результатов.
- Пустой или состоящий только из пробелов запрос не выполняет поиск.
- Поиск запускается во время ввода после debounce-задержки около 250 мс.
- Поиск не включает `ArticlePage.body`; поиск по содержимому документов остаётся out of scope.
- Новые npm/Python-зависимости не добавляются.
- Полноценные браузерные тесты autocomplete не требуются для первой версии.

## Review Focus

- Пробелы, пустой запрос и URL-кодированные символы должны возвращать предсказуемый JSON без лишнего поиска — тест `test_search_trims_query_and_returns_empty_for_blank_or_unknown` в Task 1.
- Опубликованная страница, скрытая из меню, должна находиться, а draft и корневая HomePage — нет — тест `test_search_includes_hidden_live_page_but_excludes_draft_and_root` в Task 1.
- Совпадение только в `body` не должно выдавать страницу — тест `test_search_does_not_match_body_only` в Task 1.
- При большом числе совпадений dropdown должен получать ровно максимум 10 результатов — тест `test_search_limits_results_to_ten` в Task 1.
- Быстрый ввод, HTML-подобный заголовок и Escape не должны приводить к stale-результатам, XSS или застрявшему dropdown — ручной regression-check в Task 4 и source smoke-test `test_frontend_search_code_is_present` в Task 3.

---

### Task 1: Add the Wagtail JSON search endpoint

**Files:**
- Create: `home/views.py`
- Modify: `config/urls.py`
- Create: `home/tests/test_search.py`

**Interfaces:**
- Consumes: Wagtail `Site.find_for_request(request)`, `Page.objects.live().descendant_of(root).search(query)`, and the existing `HomePage`/`ArticlePage` test setup pattern.
- Produces: `home.views.search(request) -> JsonResponse`, routed at `/search/`; JSON shape is `{"results": [{"title": str, "url": str}]}`.

- [ ] **Step 1: Write the failing backend tests**

Create `SearchViewTests(TestCase)` with a published `HomePage`, a published visible article, a published article with `show_in_menus=False`, a draft article, and a published article whose body contains a term absent from its title. Add these exact behaviors:

```python
def test_search_returns_case_insensitive_live_page_title_and_url(self):
    response = self.client.get("/search/?q=VISIBLE")
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json()["results"], [{"title": "Visible page", "url": self.visible.url}])

def test_search_includes_hidden_live_page_but_excludes_draft_and_root(self):
    results = self.client.get("/search/?q=page").json()["results"]
    titles = [item["title"] for item in results]
    self.assertIn("Hidden page", titles)
    self.assertNotIn("Draft page", titles)
    self.assertNotIn("Demo Home", titles)

def test_search_does_not_match_body_only(self):
    results = self.client.get("/search/?q=body-only-term").json()["results"]
    self.assertEqual(results, [])

def test_search_trims_query_and_returns_empty_for_blank_or_unknown(self):
    trimmed = self.client.get("/search/?q=%20Visible%20").json()["results"]
    self.assertEqual(trimmed[0]["title"], "Visible page")
    self.assertEqual(self.client.get("/search/?q=%20%20").json(), {"results": []})
    self.assertEqual(self.client.get("/search/?q=unknown").json(), {"results": []})

def test_search_limits_results_to_ten(self):
    # Create and publish 12 ArticlePage instances whose titles contain "Result".
    results = self.client.get("/search/?q=Result").json()["results"]
    self.assertEqual(len(results), 10)

def test_search_rejects_post(self):
    self.assertEqual(self.client.post("/search/", {"q": "Visible"}).status_code, 405)
```

Also cover the no-site fallback by temporarily removing the matching `Site` and asserting `{"results": []}` rather than a server error.

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `python manage.py test home.tests.test_search -v 2`

Expected: FAIL because `/search/` is not routed and `home.views.search` does not exist.

- [ ] **Step 3: Implement `search(request: HttpRequest) -> JsonResponse` in `home/views.py`**

Use `@require_GET`, trim `request.GET.get("q", "")`, return the empty JSON contract for blank input or a missing Site, and query only live descendants of `site.root_page`, excluding the root itself. Call Wagtail `.search(query)` and slice to `[:10]`; serialize only `title` and `url`.

- [ ] **Step 4: Route the view in `config/urls.py`**

Add `path("search/", search, name="page-search")` before the catch-all `path("", include(wagtail_urls))`, importing `search` from `home.views`.

- [ ] **Step 5: Run the focused tests to verify they pass**

Run: `python manage.py test home.tests.test_search -v 2`

Expected: PASS for the JSON contract, live/menu/root/body-only/limit behavior, missing Site fallback, and method restriction.

- [ ] **Step 6: Commit the backend endpoint**

```bash
git add home/views.py home/tests/test_search.py config/urls.py
git commit -m "feat: add Wagtail page title search endpoint"
```

### Task 2: Add the accessible navbar search form and dropdown container

**Files:**
- Modify: `home/templates/home/base.html`
- Modify: `home/tests/test_pages.py`

**Interfaces:**
- Consumes: `/search/` route from Task 1.
- Produces: stable DOM contract for Task 3: form `#pageSearchForm`, input `#pageSearchInput` with `name="q"`, results container `#pageSearchResults`, and `aria-controls="pageSearchResults"`/`aria-expanded` on the input.

- [ ] **Step 1: Write the failing template integration test**

Add `test_base_template_contains_page_search_form_and_dropdown` to `PublicPageTests`:

```python
def test_base_template_contains_page_search_form_and_dropdown(self):
    response = self.client.get("/")
    self.assertContains(response, '<form id="pageSearchForm"')
    self.assertContains(response, 'action="/search/"')
    self.assertContains(response, 'role="search"')
    self.assertContains(response, 'id="pageSearchInput"')
    self.assertContains(response, 'name="q"')
    self.assertContains(response, 'aria-controls="pageSearchResults"')
    self.assertContains(response, 'aria-expanded="false"')
    self.assertContains(response, 'id="pageSearchResults"')
    self.assertContains(response, 'role="listbox"')
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python manage.py test home.tests.test_pages.PublicPageTests.test_base_template_contains_page_search_form_and_dropdown -v 2`

Expected: FAIL because the base template has no search form or results container.

- [ ] **Step 3: Add the navbar form and dropdown markup to `home/templates/home/base.html`**

Place a Bootstrap-compatible `role="search"` form inside the existing collapsed navbar. Use the exact IDs from the Interfaces block, a visible/accessible Russian label such as `Поиск по страницам`, a submit button, and a relatively positioned wrapper. Initially hide the results container, set `aria-expanded="false"`, and leave result item rendering to JavaScript. Keep the existing toggler and navigation items unchanged.

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `python manage.py test home.tests.test_pages.PublicPageTests.test_base_template_contains_page_search_form_and_dropdown -v 2`

Expected: PASS, with the existing navbar, navigation, rich-text, and asset assertions still passing.

- [ ] **Step 5: Commit the navbar contract**

```bash
git add home/templates/home/base.html home/tests/test_pages.py
git commit -m "feat: add navbar page search form"
```

### Task 3: Implement debounced autocomplete rendering

**Files:**
- Modify: `frontend/main.js`
- Modify: `home/tests/test_assets.py`

**Interfaces:**
- Consumes: DOM contract from Task 2 and JSON contract from Task 1.
- Produces: `setupPageSearch() -> void` initialization and `renderSearchResults(container, results) -> void`, with debounced `GET` requests using the form action, safe result rendering, loading/empty states, stale-request protection, outside-click closing, Escape closing, and keyboard navigation.

- [ ] **Step 1: Write the failing frontend source smoke test**

Add `test_frontend_search_code_is_present` to `AssetBuildTests`, reading `frontend/main.js` and asserting it contains `setupPageSearch`, `AbortController`, `pageSearchInput`, and `pageSearchResults`. This complements the Django endpoint tests without adding a new JavaScript test framework.

- [ ] **Step 2: Run the focused asset test to verify it fails**

Run: `python manage.py test home.tests.test_assets.AssetBuildTests.test_frontend_search_code_is_present -v 2`

Expected: FAIL because `frontend/main.js` currently imports Bootstrap only.

- [ ] **Step 3: Implement `setupPageSearch()` and `renderSearchResults(container, results)` in `frontend/main.js`**

Keep the existing Bootstrap imports and call `setupPageSearch()` after defining it. Initialize only when `#pageSearchForm`, `#pageSearchInput`, and `#pageSearchResults` exist. On input, debounce approximately 250 ms, trim the query, cancel the previous `AbortController`, fetch the form action with `URLSearchParams`, and ignore aborted/stale responses. Prevent the form's default submit and run the current query immediately. Render loading and `Ничего не найдено` states, create result links with `document.createElement`/`textContent` (never server data in `innerHTML`), toggle `hidden` and `aria-expanded`, close on empty input/outside click/Escape, and support ArrowUp/ArrowDown by moving focus among result links, Tab by normal focus order, and Escape by returning focus to the input without hijacking unrelated navbar controls.

- [ ] **Step 4: Run the focused asset test to verify it passes**

Run: `python manage.py test home.tests.test_assets.AssetBuildTests.test_frontend_search_code_is_present -v 2`

Expected: PASS.

- [ ] **Step 5: Build the frontend bundle**

Run: `npm run build`

Expected: esbuild completes successfully and regenerates ignored `static/site/main.css` and `static/site/main.js` containing Bootstrap and the search client code.

- [ ] **Step 6: Run the existing asset tests**

Run: `python manage.py test home.tests.test_assets -v 2`

Expected: PASS, including non-empty Bootstrap CSS/JS and search source smoke assertions.

- [ ] **Step 7: Commit the autocomplete client**

```bash
git add frontend/main.js home/tests/test_assets.py
git commit -m "feat: add navbar search autocomplete"
```

### Task 4: Run full verification and manual regression checks

**Files:**
- No source changes expected.

**Interfaces:**
- Consumes: completed backend, template, and frontend tasks.
- Produces: verified working branch with no whitespace errors and documented manual acceptance evidence.

- [ ] **Step 1: Run Django system checks**

Run: `python manage.py check`

Expected: `System check identified no issues`.

- [ ] **Step 2: Run the complete Django test suite**

Run: `python manage.py test -v 2`

Expected: all project tests pass, including search, navigation, rich text, seed, and asset tests.

- [ ] **Step 3: Perform the browser regression check**

Run the development server and verify: typing a title shows results after the debounce; a hidden live page appears; a draft does not; empty input hides the list; `Ничего не найдено` appears for an unknown query; clicking a result navigates; Escape and outside click close the list; rapidly typing two queries leaves only the newest response visible; a title containing `<`/`>` is rendered as text; and the mobile Bootstrap toggler still opens and closes the navbar.

- [ ] **Step 4: Check the final diff**

Run: `git diff --check && git status --short`

Expected: no whitespace errors; only intentional committed changes remain, and ignored frontend bundles are not added to Git.
