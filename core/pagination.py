
PAGE_SIZE_OPTIONS = (10, 15, 20)
DEFAULT_PAGE_SIZE = 10


def get_page_size(request, session_key):
    raw = request.GET.get("page_size")

    if raw:
        try:
            selected = int(raw)
        except (TypeError, ValueError):
            selected = None

        if selected in PAGE_SIZE_OPTIONS:
            request.session[session_key] = selected

    saved = request.session.get(session_key, DEFAULT_PAGE_SIZE)
    return saved if saved in PAGE_SIZE_OPTIONS else DEFAULT_PAGE_SIZE


class PageSizeMixin:
    page_size_session_key = "page_size"

    def get_paginate_by(self, queryset):
        return get_page_size(
            self.request,
            self.page_size_session_key,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_size"] = get_page_size(
            self.request,
            self.page_size_session_key,
        )
        context["page_size_options"] = PAGE_SIZE_OPTIONS
        return context
