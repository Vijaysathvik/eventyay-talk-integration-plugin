"""
templatetags/eti_tags.py — Template tags for the integration plugin
====================================================================
Two tags:

  {% eti_nav_items event %}
    Returns a list of nav item dicts based on IntegrationSettings.
    Used in the event's public navigation template to show/hide the
    Tickets and Video links without touching core nav code.

  {% eti_plugin_active event as is_active %}
    Assignment tag.  True if this plugin is in event.plugins.
"""

import logging

from django import template

logger = logging.getLogger(__name__)
register = template.Library()

_PLUGIN_LABEL = "eventyay_talk_integration"


@register.simple_tag
def eti_nav_items(event) -> list:
    """
    Return a list of ``{key, label, url}`` dicts for this event's nav,
    based on the plugin's IntegrationSettings.

    If the plugin isn't active for the event, or if anything goes wrong
    reading the settings, we return an empty list.  The nav silently
    shows nothing rather than throwing a 500.

    Results are cached on the request object (using a ``_eti_nav_cache``
    dict) so repeated calls in the same template render don't hit the DB
    multiple times.  We don't use Django's cache framework here because
    nav items are per-request and per-event, not shared across requests.
    """
    if not _plugin_active(event):
        return []

    # Try to use the request-level cache.  This tag is called inside
    # {% for %} loops in some nav templates, so the cache matters.
    cache_key = f"nav_{event.pk}"
    if hasattr(event, "_eti_cache"):
        cached = event._eti_cache.get(cache_key)
        if cached is not None:
            return cached

    try:
        from ..models import IntegrationSettings  # noqa: PLC0415

        settings = IntegrationSettings.for_event(event)
    except Exception as exc:
        logger.warning("eti_nav_items: could not load settings for %s: %s", event, exc)
        return []

    items = []
    if settings.show_tickets_in_nav:
        items.append(
            {
                "key": "tickets",
                "label": settings.tickets_nav_label or "Tickets",
                "url": "tickets/",
            }
        )
    if settings.show_video_in_nav:
        items.append(
            {
                "key": "video",
                "label": "Join Online Video",
                "url": "video/",
            }
        )

    # Store in event-level dict so we avoid repeated DB hits within one render.
    if not hasattr(event, "_eti_cache"):
        event._eti_cache = {}
    event._eti_cache[cache_key] = items

    return items


@register.simple_tag
def eti_plugin_active(event) -> bool:
    """
    Return True if the integration plugin is active for this event.

    Usage::

        {% eti_plugin_active event as is_active %}
        {% if is_active %}...{% endif %}
    """
    return _plugin_active(event)


def _plugin_active(event) -> bool:
    """Check event.plugins for our label.  Returns False on any error."""
    try:
        plugins: str = getattr(event, "plugins", "") or ""
        return _PLUGIN_LABEL in plugins
    except Exception:
        return False
