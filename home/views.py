from typing import cast

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET
from wagtail.models import Page, Site


@require_GET
def search(request: HttpRequest) -> JsonResponse:
    query = cast(str, request.GET.get("q", "")).strip()
    if not query:
        return JsonResponse({"results": []})

    site = Site.find_for_request(request)
    if site is None:
        return JsonResponse({"results": []})

    pages = Page.objects.live().descendant_of(site.root_page).search(query)[:10]
    return JsonResponse(
        {
            "results": [
                {"title": page.title, "url": page.url}
                for page in pages
            ]
        }
    )
