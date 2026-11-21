"""Admin inbox for messages sent from the About page's contact form."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ..models import ContactMessage
from .dashboard import _require_admin

PER_PAGE = 15
SHOW = {
    "open": ("Open", Q(is_handled=False)),
    "handled": ("Handled", Q(is_handled=True)),
    "all": ("All", Q()),
}


def index(request):
    _require_admin(request)
    show = request.GET.get("show", "open")
    if show not in SHOW:
        show = "open"
    q = request.GET.get("q", "").strip()

    counts = ContactMessage.objects.aggregate(
        **{key: Count("pk", filter=query) for key, (_, query) in SHOW.items()}
    )
    items = ContactMessage.objects.filter(SHOW[show][1])
    if q:
        items = items.filter(
            Q(name__icontains=q) | Q(email__icontains=q) | Q(subject__icontains=q) | Q(message__icontains=q)
        )
    page = Paginator(items, PER_PAGE).get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "admin/inquiries.html", {
        "page": page,
        "show": show,
        "q": q,
        "tabs": [(key, label, counts[key]) for key, (label, _) in SHOW.items()],
        "query_string": params.urlencode(),
    })


def _back(request):
    target = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                       require_https=request.is_secure()):
        return redirect(target)
    return redirect("inquiries")


@require_POST
def toggle(request, pk):
    """Mark an inquiry handled, or open it again."""
    _require_admin(request)
    item = get_object_or_404(ContactMessage, pk=pk)
    item.is_handled = not item.is_handled
    item.save(update_fields=["is_handled"])
    state = "marked as handled" if item.is_handled else "reopened"
    messages.success(request, f"Message from {item.name} {state}.")
    return _back(request)


@require_POST
def delete(request, pk):
    _require_admin(request)
    item = get_object_or_404(ContactMessage, pk=pk)
    item.delete()
    messages.success(request, f"Message from {item.name} was deleted.")
    return _back(request)
