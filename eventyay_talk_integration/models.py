"""
models.py — Plugin configuration models
=========================================
Three models:
  IntegrationSettings  — per-event feature toggles (OneToOne with Event)
  MCAssignment         — assigns a team member as MC to a video room
  SyncLog              — append-only audit trail for all sync operations
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class IntegrationSettings(models.Model):
    """
    Per-event configuration for the integration plugin.
    One row per event. Created on first access via for_event().
    """

    event = models.OneToOneField(
        "eventyay.Event",
        on_delete=models.CASCADE,
        related_name="integration_settings",
        verbose_name=_("Event"),
    )

    # ── Video sync ──
    video_sync_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enable Talk → Video sync"),
        help_text=_(
            "Automatically create and update video rooms when "
            "Talk sessions are created or modified."
        ),
    )
    inject_speaker_profile = models.BooleanField(
        default=True,
        verbose_name=_("Inject speaker profiles into video rooms"),
        help_text=_(
            "Show speaker name, bio, and photo inside the video room UI."
        ),
    )
    video_sync_mode = models.CharField(
        max_length=20,
        choices=[
            ("realtime", _("Real-time (on save)")),
            ("periodic", _("Periodic (every 5 min)")),
            ("manual", _("Manual only")),
        ],
        default="realtime",
        verbose_name=_("Sync mode"),
    )

    # ── Ticket gating ──
    ticket_gate_enabled = models.BooleanField(
        default=False,
        verbose_name=_("Gate video access by ticket"),
        help_text=_(
            "Require a valid ticket purchase to join video rooms."
        ),
    )

    # ── Navigation visibility (extends issue #2482) ──
    show_tickets_in_nav = models.BooleanField(
        default=True,
        verbose_name=_("Show Tickets in public nav"),
    )
    show_video_in_nav = models.BooleanField(
        default=True,
        verbose_name=_("Show Join Online Video in public nav"),
    )
    tickets_nav_label = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Custom Tickets nav label"),
        help_text=_("Leave blank to use default 'Tickets'."),
    )

    # ── MC assignment ──
    mc_notifications_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Email MC on room assignment"),
    )
    mc_permission_level = models.CharField(
        max_length=20,
        choices=[
            ("view", _("View only")),
            ("moderate", _("Moderate (mute/kick)")),
            ("host", _("Host (full control)")),
        ],
        default="moderate",
        verbose_name=_("MC permission level"),
    )

    class Meta:
        verbose_name = _("Integration Settings")
        verbose_name_plural = _("Integration Settings")

    def __str__(self):
        return f"IntegrationSettings for {self.event}"

    @classmethod
    def for_event(cls, event):
        """
        Get or create settings for an event.
        Safe to call anywhere — returns defaults on first call.
        """
        obj, _ = cls.objects.get_or_create(event=event)
        return obj


class MCAssignment(models.Model):
    """
    Assigns a team member as MC (Master of Ceremony) for a video room.
    Created via the admin UI; triggers a notification signal on save.
    """

    event = models.ForeignKey(
        "eventyay.Event",
        on_delete=models.CASCADE,
        related_name="mc_assignments",
    )
    video_room_id = models.CharField(
        max_length=200,
        verbose_name=_("Video room ID"),
    )
    team_member = models.ForeignKey(
        "eventyay.TeamMember",
        on_delete=models.CASCADE,
        related_name="mc_assignments",
        verbose_name=_("MC"),
    )
    session_title = models.CharField(max_length=300, blank=True)
    permission_level = models.CharField(
        max_length=20,
        choices=[
            ("view", _("View only")),
            ("moderate", _("Moderate (mute/kick)")),
            ("host", _("Host (full control)")),
        ],
        default="moderate",
        verbose_name=_("Permission level"),
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    notified = models.BooleanField(default=False)

    class Meta:
        unique_together = [("event", "video_room_id", "team_member")]
        verbose_name = _("MC Assignment")
        verbose_name_plural = _("MC Assignments")

    def __str__(self):
        return f"MC: {self.team_member} → {self.session_title}"


class SyncLog(models.Model):
    """
    Append-only audit trail for all sync operations.
    Written by sync.py and notifications.py — never by admin users directly.
    """

    event = models.ForeignKey(
        "eventyay.Event",
        on_delete=models.CASCADE,
        related_name="integration_sync_logs",
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_("Timestamp"),
    )
    level = models.CharField(
        max_length=10,
        choices=[
            ("info", _("Info")),
            ("warn", _("Warning")),
            ("error", _("Error")),
        ],
        default="info",
        db_index=True,
        verbose_name=_("Level"),
    )
    action = models.CharField(
        max_length=100,
        verbose_name=_("Action"),
    )
    message = models.TextField(verbose_name=_("Message"))
    session_id = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Session ID"),
    )
    video_room_id = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Video room ID"),
    )

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = _("Sync Log")
        verbose_name_plural = _("Sync Logs")

    def __str__(self):
        return f"[{self.level}] {self.action} @ {self.timestamp:%Y-%m-%d %H:%M}"