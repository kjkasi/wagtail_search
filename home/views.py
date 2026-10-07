from collections.abc import Iterable
from html.parser import HTMLParser
from typing import cast

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET
from wagtail.documents import get_document_model
from wagtail.fields import RichTextField
from wagtail.models import Page, Site

Document = get_document_model()
MAX_SEARCH_QUERY_LENGTH = 200
MAX_SEARCH_RESULTS = 10


class _DocumentLinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._document_id: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag != "a":
            return
        attributes = dict(attrs)
        document_id = attributes.get("id")
        if (
            attributes.get("linktype") == "document"
            and document_id
            and document_id.isdigit()
        ):
            self._document_id = document_id
            self._link_text = []

    def handle_data(self, data: str):
        if self._document_id is not None:
            self._link_text.append(data)

    def handle_endtag(self, tag: str):
        if tag == "a" and self._document_id is not None:
            link_text = " ".join("".join(self._link_text).split())
            self.links.append((self._document_id, link_text))
            self._document_id = None
            self._link_text = []


def _document_links_for_pages(pages: Iterable[Page]) -> dict[str, list[str]]:
    links_by_document_id: dict[str, list[str]] = {}
    for page in pages:
        specific_page = page.specific
        for field in specific_page._meta.get_fields():
            if not isinstance(field, RichTextField):
                continue
            rich_text = field.value_from_object(specific_page)
            if not rich_text:
                continue
            parser = _DocumentLinkParser()
            parser.feed(str(rich_text))
            parser.close()
            for document_id, link_text in parser.links:
                links_by_document_id.setdefault(document_id, []).append(link_text)
    return links_by_document_id


@require_GET
def search(request: HttpRequest) -> JsonResponse:
    query = cast(str, request.GET.get("q", "")).strip()
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

    site_pages = Page.objects.live().descendant_of(site.root_page, inclusive=True)
    pages = list(site_pages.search(query)[:MAX_SEARCH_RESULTS])
    remaining_results = MAX_SEARCH_RESULTS - len(pages)

    documents = []
    if remaining_results:
        document_links_by_id = _document_links_for_pages(site_pages.specific())
        linked_document_ids = set(document_links_by_id)
        link_matching_document_ids = [
            document_id
            for document_id, link_texts in document_links_by_id.items()
            if any(
                query.casefold() in link_text.casefold()
                for link_text in link_texts
            )
        ]

        title_matching_documents = list(
            Document.objects.search(query)
            .get_queryset()
            .filter(pk__in=linked_document_ids)[:remaining_results]
        )
        documents = title_matching_documents
        link_matching_documents = {
            str(document.pk): document
            for document in Document.objects.filter(pk__in=link_matching_document_ids)
        }
        seen_document_ids = {str(document.pk) for document in documents}
        for document_id in link_matching_document_ids:
            if len(documents) >= remaining_results:
                break
            if (
                document_id not in seen_document_ids
                and document_id in link_matching_documents
            ):
                documents.append(link_matching_documents[document_id])
                seen_document_ids.add(document_id)

    results = [
        {"type": "page", "title": page.title, "url": page.url}
        for page in pages
    ] + [
        {"type": "document", "title": document.title, "url": document.url}
        for document in documents
    ]
    return JsonResponse({"results": results[:10]})
