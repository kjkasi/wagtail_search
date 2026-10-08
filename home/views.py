from html.parser import HTMLParser
from typing import Iterable, Iterator

from django.db.models import Q
from django.http import HttpRequest, JsonResponse
from wagtail.documents.models import Document
from wagtail.models import Page, Site

from home.models import ArticlePage, SectionPage


MAX_SEARCH_QUERY_LENGTH: int = 200
MAX_SEARCH_RESULTS: int = 10
DOCUMENT_BATCH_SIZE: int = 100
MAX_DOCUMENT_PK = 2**63 - 1


class _DocumentLinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._active_links: list[list[str]] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attributes = dict(attrs)
        document_id = attributes.get("id", "")
        if (
            attributes.get("linktype") == "document"
            and document_id.isascii()
            and document_id.isdecimal()
        ):
            self._active_links.append([document_id, ""])

    def handle_data(self, data):
        if self._active_links:
            self._active_links[-1][1] += data

    def handle_endtag(self, tag):
        if tag != "a" or not self._active_links:
            return
        document_id, text = self._active_links.pop()
        normalized_text = " ".join(text.split())
        self.links.append((document_id, normalized_text))


def _document_links_for_pages(pages: Iterable[Page]) -> Iterator[tuple[str, str]]:
    for page in pages:
        specific_page = page.specific
        body = getattr(specific_page, "body", "")
        if not body:
            continue
        parser = _DocumentLinkParser()
        parser.feed(str(body))
        parser.close()
        yield from parser.links


def _normalized_document_id(document_id: str) -> str | None:
    if not document_id.isascii() or not document_id.isdecimal():
        return None
    value = int(document_id)
    if value > MAX_DOCUMENT_PK:
        return None
    return str(value)


def _documents_for_ids_in_order(
    document_ids: Iterable[str], limit: int
) -> list[Document]:
    if limit <= 0:
        return []

    documents = []
    seen_ids = set()
    batch_ids = []

    def consume_batch(ids):
        by_id = {
            str(document.pk): document
            for document in Document.objects.filter(
                pk__in=[int(document_id) for document_id in ids]
            )
        }
        return [by_id[document_id] for document_id in ids if document_id in by_id]

    for document_id in document_ids:
        normalized_id = _normalized_document_id(document_id)
        if normalized_id is None or normalized_id in seen_ids:
            continue
        seen_ids.add(normalized_id)
        batch_ids.append(normalized_id)
        if len(batch_ids) < DOCUMENT_BATCH_SIZE:
            continue
        documents.extend(consume_batch(batch_ids))
        if len(documents) >= limit:
            return documents[:limit]
        batch_ids = []

    if batch_ids:
        documents.extend(consume_batch(batch_ids))
    return documents[:limit]


def _page_url(page: Page, request: HttpRequest) -> str:
    return page.get_url(request=request) or page.url


def _document_url(document: Document, request: HttpRequest) -> str:
    return request.build_absolute_uri(document.url)


def _document_score(document: Document, query: str) -> int:
    title = document.title.casefold()
    normalized_query = query.casefold()
    if title == normalized_query:
        return 3
    if title.startswith(normalized_query):
        return 2
    return 1


def _search_pages(queryset, query: str) -> list[Page]:
    indexed_results = list(queryset.search(query))
    seen_ids = {page.pk for page in indexed_results}
    fallback_results = queryset.filter(
        Q(title__icontains=query) | Q(body__icontains=query)
    )
    return indexed_results + [
        page for page in fallback_results if page.pk not in seen_ids
    ]


def search(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"results": []}, status=405)

    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"results": []})
    if len(query) > MAX_SEARCH_QUERY_LENGTH:
        return JsonResponse(
            {"error": "query_too_long", "results": []},
            status=400,
        )

    site = Site.find_for_request(request)
    if site is None:
        return JsonResponse({"results": []})

    sections = list(SectionPage.objects.child_of(site.root_page).live().public())
    article_ids = []
    for section in sections:
        article_ids.extend(
            ArticlePage.objects.child_of(section).values_list("id", flat=True)
        )
    articles = ArticlePage.objects.filter(pk__in=article_ids).live().public()

    page_results = _search_pages(articles, query)[:MAX_SEARCH_RESULTS]
    results = [
        {
            "type": "page",
            "title": page.title,
            "url": _page_url(page, request),
        }
        for page in page_results
    ]

    if len(results) >= MAX_SEARCH_RESULTS:
        return JsonResponse({"results": results})

    document_links = list(_document_links_for_pages(articles))
    document_ids = []
    link_texts = {}
    for document_id, link_text in document_links:
        normalized_id = _normalized_document_id(document_id)
        if normalized_id is None:
            continue
        if normalized_id not in link_texts:
            document_ids.append(normalized_id)
            link_texts[normalized_id] = []
        link_texts[normalized_id].append(link_text)

    title_matches = []
    visible_matches = set()
    documents_by_id = {}
    normalized_query = query.casefold()
    for start in range(0, len(document_ids), DOCUMENT_BATCH_SIZE):
        batch_ids = document_ids[start : start + DOCUMENT_BATCH_SIZE]
        documents = _documents_for_ids_in_order(batch_ids, len(batch_ids))
        documents_by_id = {str(document.pk): document for document in documents}
        documents_by_id.update(
            {str(document.pk): document for document in documents}
        )
        document_queryset = Document.objects.filter(
            pk__in=[document.pk for document in documents]
        )
        search_results = list(document_queryset.search(query))
        fallback_results = document_queryset.filter(title__icontains=query)
        matched_ids = {
            str(document.pk) for document in search_results
        } | {str(document.pk) for document in fallback_results}
        for order, document_id in enumerate(batch_ids):
            document = documents_by_id.get(document_id)
            if document is None:
                continue
            if document_id in matched_ids:
                title_matches.append(
                    (
                        _document_score(document, query),
                        order + start,
                        document,
                    )
                )
            if any(
                normalized_query in link_text.casefold()
                for link_text in link_texts[document_id]
            ):
                visible_matches.add(document_id)

    title_matches.sort(key=lambda item: (-item[0], item[1]))
    ordered_documents = [item[2] for item in title_matches]
    seen_documents = {document.pk for document in ordered_documents}
    for document_id in document_ids:
        if document_id in visible_matches:
            document = documents_by_id.get(document_id)
            if document is not None and document.pk not in seen_documents:
                ordered_documents.append(document)
                seen_documents.add(document.pk)

    remaining = MAX_SEARCH_RESULTS - len(results)
    results.extend(
        {
            "type": "document",
            "title": document.title,
            "url": _document_url(document, request),
        }
        for document in ordered_documents[:remaining]
    )
    return JsonResponse({"results": results[:MAX_SEARCH_RESULTS]})
