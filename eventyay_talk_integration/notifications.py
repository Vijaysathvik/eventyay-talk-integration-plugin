"""
notifications.py — MC assignment email notification
=====================================================
Single public function: notify_mc_assigned(assignment).

eventyay (pretix-based) has its own mail queue; in production you'd use
pretix's QueuedMail or EventMailSetting.send_mail().  We fall back to
django.core.mail.send_mail() here so the code works standalone, but the
comment in _send() explains exactly what the production swap looks like.

All exceptions are caught and logged — a notification failure should never
roll back an MC assignment.
"""

import logging
from typing import TYPE_CHECKING

from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from .models import MCAssignment

logger = logging.getLogger(__name__)

_TEMPLATE = "eventyay_talk_integration/mail/mc_assigned.txt"


def notify_mc_assigned(assignment: "MCAssignment") -> None:
    """
    Send an email to the MC informing them of their room assignment.

    Marks assignment.notified = True after a successful send.  If sending
    fails for any reason the assignment record is left unchanged so an
    organiser can retry from the admin list view or the API.
    """
    try:
        _send(assignment)
        assignment.notified = True
        assignment.save(update_fields=["notified"])
        _log_success(assignment)
    except Exception as exc:
        _log_failure(assignment, exc)


# ── Internal helpers ──────────────────────────────────────────────────────────


def _build_context(assignment: "MCAssignment") -> dict:
    """Assemble the template context from the assignment and related objects."""
    event = assignment.event
    mc_user = assignment.team_member.user

    # permission_level is stored as e.g. "moderate"; map to human description.
    permission_descriptions = {
        "view": _(
            "You can watch sessions and see participant lists, "
            "but cannot take any moderation actions."
        ),
        "moderate": _(
            "You can mute participants, remove disruptive attendees, "
            "and manage the room chat."
        ),
        "host": _(
            "You have full host control: start/stop the session, "
            "manage all participants, and end the call."
        ),
    }
    level = getattr(assignment, "permission_level", "moderate")
    description = permission_descriptions.get(level, "")

    # Build the settings URL the MC can use to check their assignment details.
    try:
        from django.urls import reverse  # noqa: PLC0415
        settings_url = reverse(
            "plugins:eventyay_talk_integration:settings",
            kwargs={"organiser": event.organiser.slug, "event": event.slug},
        )
    except Exception:
        settings_url = ""

    return {
        "assignment": assignment,
        "event": event,
        "mc_name": mc_user.get_full_name() or mc_user.email,
        "session_title": assignment.session_title,
        "video_room_id": assignment.video_room_id,
        "permission_level": level,
        "permission_description": description,
        "settings_url": settings_url,
        "assigned_at": timezone.localtime(assignment.assigned_at),
    }


def _send(assignment: "MCAssignment") -> None:
    """
    Render the email body and dispatch it.

    Production swap: replace the django.core.mail.send_mail() call below
    with something like:
        from pretix.base.services.mail import SendMailException, mail
        mail(
            to=recipient,
            subject=subject,
            template=_TEMPLATE,
            context=ctx,
            event=assignment.event,
            locale=assignment.event.settings.locale,
        )
    That routes through pretix's async mail queue with proper i18n and
    organiser SMTP settings.
    """
    from django.core.mail import send_mail  # noqa: PLC0415

    ctx = _build_context(assignment)
    body = render_to_string(_TEMPLATE, ctx)

    mc_email: str = assignment.team_member.user.email
    if not mc_email:
        raise ValueError(f"Team member {assignment.team_member} has no email address")

    subject = str(
        _(f"You have been assigned as MC for "{ctx['session_title']}" at {ctx['event'].name}")
    )

    send_mail(
        subject=subject,
        message=body,
        from_email=None,  # falls back to DEFAULT_FROM_EMAIL
        recipient_list=[mc_email],
        fail_silently=False,
    )

    logger.info(
        "eventyay_talk_integration: MC notification sent to %s for session '%s'",
        mc_email,
        assignment.session_title,
    )


def _log_success(assignment: "MCAssignment") -> None:
    """Write a success entry to SyncLog."""
    try:
        from .models import SyncLog  # noqa: PLC0415

        SyncLog.objects.create(
            event=assignment.event,
            level="info",
            action="mc_notification_sent",
            message=_(
                f"MC notification sent to {assignment.team_member.user.email} "
                f"for session '{assignment.session_title}'"
            ),
        )
    except Exception as exc:
        logger.warning("eventyay_talk_integration: could not write success SyncLog: %s", exc)


def _log_failure(assignment: "MCAssignment", exc: Exception) -> None:
    """Write an error entry to SyncLog and emit a logger warning."""
    logger.error(
        "eventyay_talk_integration: MC notification failed for assignment %s: %s",
        assignment.pk,
        exc,
        exc_info=True,
    )
    try:
        from .models import SyncLog  # noqa: PLC0415

        SyncLog.objects.create(
            event=assignment.event,
            level="error",
            action="mc_notification_failed",
            message=str(exc),
        )
    except Exception as log_exc:
        logger.warning(
            "eventyay_talk_integration: could not write failure SyncLog: %s", log_exc
        )
