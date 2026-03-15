"""
cleanup.py — Plugin uninstall cleanup
======================================
Called from EvenYayTalkIntegrationConfig.uninstalled() when an organiser
removes the plugin from an event.

We only delete rooms that this plugin created (plugin_managed=True).
Any video room an organiser created manually is left alone — removing the
plugin should not destroy things the organiser built themselves.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eventyay.models import Event  # pragma: no cover

logger = logging.getLogger(__name__)


def remove_plugin_managed_rooms(event: "Event") -> int:
    """
    Delete all VideoRoom objects tagged plugin_managed=True for this event.

    Returns the count of deleted rooms.  Caller (uninstalled() hook) can
    log or display this number to the organiser.

    SyncLog writes are best-effort: if the event is mid-deletion and the
    SyncLog table is already gone, we fall back to the Python logger.
    """
    _write_pre_deletion_log(event)

    try:
        from eventyay.video.models import VideoRoom  # noqa: PLC0415

        qs = VideoRoom.objects.filter(event=event, plugin_managed=True)
        count, _ = qs.delete()
    except Exception as exc:
        logger.error(
            "eventyay_talk_integration: failed to delete plugin-managed rooms "
            "for event '%s': %s",
            getattr(event, "slug", str(event)),
            exc,
            exc_info=True,
        )
        return 0

    logger.info(
        "eventyay_talk_integration: removed %d plugin-managed video room(s) "
        "from event '%s'",
        count,
        getattr(event, "slug", str(event)),
    )
    return count


def _write_pre_deletion_log(event: "Event") -> None:
    """
    Write a SyncLog entry before deletion so there's an audit trail even if
    the plugin is fully uninstalled afterwards.

    This is intentionally fire-and-forget: if it fails (e.g. the plugin's
    database tables were already dropped), we log to the Python logger and
    continue.  The room deletion must not be blocked by a log write failure.
    """
    try:
        from .models import SyncLog  # noqa: PLC0415

        SyncLog.objects.create(
            event=event,
            level="info",
            action="plugin_uninstalled",
            message=(
                "Plugin uninstalled — removing all plugin-managed video rooms."
            ),
        )
    except Exception as exc:
        # Tables might not exist yet if this is called during a failed install.
        logger.warning(
            "eventyay_talk_integration: could not write pre-deletion SyncLog "
            "for event '%s': %s",
            getattr(event, "slug", str(event)),
            exc,
        )
