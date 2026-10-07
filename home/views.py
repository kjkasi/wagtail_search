from collections.abc import Iterable, Iterator
from html.parser import HTMLParser
from itertools import islice

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET
from wagtail.documents import get_document_model
from wagtail.fields import RichTextField
from wagtail.models import Page, Site

Document = get_document_model()
MAX_SEARCH_QUERY_LENGTH = 200
MAX_SEARCH_RESULTS = 10
DOCUMENT_BATCH_SIZE = 100


class _DocumentLinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._anchors: list[tuple[str | None, list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag != "a":
            return
        attributes = dict(attrs)
        document_id = attributes.get("id")
        if not (
            attributes.get("linktype") == "document"
            and document_id
            and document_id.isdigit()
        ):
            document_id = None
        self._anchors.append((document_id, []))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str):
        for document_id, link_text in self._anchors:
            if document_id is not None:
                link_text.append(data)

    def handle_endtag(self, tag: str):
        if tag != "a" or not self._anchors:
            return
        document_id, link_text = self._anchors.pop()
        if document_id is not None:
            self.links.append((document_id, " ".join("".join(link_text).split())))

    def close(self):
        super().close()
        while self._anchors:
            self.handle_endtag("a")


def _document_links_for_pages(
    pages: Iterable[Page],
) -> Iterator[tuple[str, str]]:
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
            yield from parser.links


def _documents_for_ids_in_order(
    document_ids: Iterable[str], limit: int,
) -> list[Document]:
    documents: list[Document] = []
    document_ids_iterator = iter(document_ids)
    while len(documents) < limit:
        batch_ids = list(islice(document_ids_iterator, DOCUMENT_BATCH_SIZE))
        if not batch_ids:
            break
        documents_by_id = {
            str(document.pk): document
            for document in Document.objects.filter(pk__in=batch_ids)
        }
        for document_id in batch_ids:
            document = documents_by_id.get(document_id)
            if document is None:
                continue
            documents.append(document)
            if len(documents) == limit:
                return documents
    return documents


@require_GET
def search(request: HttpRequest) -> JsonResponse:
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

    site_pages = (
        Page.objects.live()
        .public()
        .descendant_of(site.root_page, inclusive=True)
    )
    pages = list(site_pages.search(query)[:MAX_SEARCH_RESULTS])
    remaining_results = MAX_SEARCH_RESULTS - len(pages)

    documents: list[Document] = []
    if remaining_results:
        document_links_by_id: dict[str, list[str]] = {}
        for document_id, link_text in _document_links_for_pages(
            site_pages.specific().iterator(chunk_size=DOCUMENT_BATCH_SIZE)
        ):
            document_links_by_id.setdefault(document_id, []).append(link_text)

        linked_document_ids = set(document_links_by_id)
        documents = list(
            Document.objects.filter(pk__in=linked_document_ids).search(
                query, fields=["title"]
            )[:remaining_results]
        )
        seen_document_ids = {str(document.pk) for document in documents}
        link_matching_document_ids = (
            document_id
            for document_id, link_texts in document_links_by_id.items()
            if any(
                query.casefold() in link_text.casefold()
                for link_text in link_texts
            )
            and document_id not in seen_document_ids
        )
        documents.extend(
            _documents_for_ids_in_order(
                link_matching_document_ids,
                remaining_results - len(documents),
            )
        )

    results = [
        {"type": "page", "title": page.title, "url": page.url}
        for page in pages
    ] + [
        {"type": "document", "title": document.title, "url": document.url}
        for document in documents
    ]
    return JsonResponse({"results": results[:10]})
