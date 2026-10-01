import re
from typing import cast

from django.db.models import Q
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET
from wagtail.documents import get_document_model
from wagtail.models import Page, Site

from home.models import ArticlePage

Document = get_document_model()
MAX_SEARCH_QUERY_LENGTH = 200
MAX_SEARCH_RESULTS = 10
DOCUMENT_LINK_RE = re.compile(
    r'<a\b(?=[^>]*\blinktype=["\']document["\'])'
    r'(?=[^>]*\bid=["\'](\d+)["\'])[^>]*>',
)


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

    pages = list(
        Page.objects.live().descendant_of(site.root_page).search(query)[
            :MAX_SEARCH_RESULTS
        ]
    )
    remaining_results = MAX_SEARCH_RESULTS - len(pages)
    matching_documents = (
        list(Document.objects.search(query)[:remaining_results])
        if remaining_results
        else []
    )

    attached_document_ids: set[str] = set()
    if matching_documents:
        document_link_query: Q = Q()
        candidate_document_ids = {str(document.pk) for document in matching_documents}
        for document_id in candidate_document_ids:
            document_link_query = cast(
                Q,
                document_link_query | Q(body__contains=f'id="{document_id}"'),
            )
            document_link_query = cast(
                Q,
                document_link_query | Q(body__contains=f"id='{document_id}'"),
            )

        article_pages = (
            ArticlePage.objects.live()
            .descendant_of(site.root_page)
            .filter(
                document_link_query
                & (
                    Q(body__contains='linktype="document"')
                    | Q(body__contains="linktype='document'")
                )
            )
            .only("body")
        )
        attached_document_ids = {
            document_id
            for page in article_pages
            for document_id in DOCUMENT_LINK_RE.findall(page.body)
            if document_id in candidate_document_ids
        }

    documents = [
        document
        for document in matching_documents
        if str(document.pk) in attached_document_ids
    ]

    results = [
        {"type": "page", "title": page.title, "url": page.url}
        for page in pages
    ] + [
        {"type": "document", "title": document.title, "url": document.url}
        for document in documents
    ]
    return JsonResponse({"results": results[:10]})
