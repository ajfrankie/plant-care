from django.utils.functional import cached_property


class HeaderNotifications:
    """The header bell's unread count and latest notifications.

    Only queried (and synced) when a page's header actually uses it.
    """

    LATEST = 5

    def __init__(self, request):
        self.request = request
        self.user = request.user

    @cached_property
    def _visible(self):
        from . import notify
        from .models import Notification
        if not getattr(self.request, "notifications_synced", False):
            notify.sync(self.user)
        return Notification.objects.filter(recipient=self.user, is_dismissed=False)

    @cached_property
    def unread(self):
        return self._visible.filter(is_read=False).count()

    @cached_property
    def latest(self):
        from .controllers.notifications import _decorate
        return _decorate(list(self._visible.select_related("task")[: self.LATEST]))


def notifications(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"header_notifications": HeaderNotifications(request)}


def admin_counts(request):
    """Open contact-form inquiries, for the admin sidebar badge (queried only when shown)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.is_staff:
        return {}
    from django.utils.functional import SimpleLazyObject
    from .models import ContactMessage
    return {"open_inquiries": SimpleLazyObject(
        lambda: ContactMessage.objects.filter(is_handled=False).count()
    )}
