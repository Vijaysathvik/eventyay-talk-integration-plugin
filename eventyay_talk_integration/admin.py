"""
admin.py — Django admin registration for the integration plugin
================================================================
Three model admins:
  IntegrationSettingsAdmin  — per-event feature toggles
  MCAssignmentAdmin         — assign/view MC assignments
  SyncLogAdmin              — read-only audit trail

The SyncLogAdmin is intentionally locked down: log records are written
exclusively by sync.py and notifications.py, never by an admin user.
Allowing edits would break the audit guarantee.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import IntegrationSettings, MCAssignment, SyncLog

# Colour map for the level badge in the sync log list view.
_LEVEL_COLOURS = {
    "info": "#2e7d32",
    "warn": "#e65100",
    "error": "#c62828",
}


@admin.register(IntegrationSettings)
class IntegrationSettingsAdmin(admin.ModelAdmin):
    """Per-event integration configuration."""

    list_display = [
        "event",
        "video_sync_enabled",
        "ticket_gate_enabled",
        "show_tickets_in_nav",
    ]
    list_filter = ["video_sync_enabled", "ticket_gate_enabled"]
    search_fields = ["event__name", "event__slug"]

    fieldsets = [
        (
            _("Talk → Video Sync"),
            {
                "fields": [
                    "video_sync_enabled",
                    "video_sync_mode",
                    "inject_speaker_profile",
                ],
                "description": _(
                    "Controls how Talk sessions are mirrored as video rooms. "
                    "Sync mode 'real-time' fires on every save; 'periodic' "
                    "requires the Celery beat task to be running."
                ),
            },
        ),
        (
            _("Ticket Access Gate"),
            {
                "fields": ["ticket_gate_enabled"],
                "description": _(
                    "When enabled, a valid ticket is required to join any "
                    "video room associated with this event."
                ),
            },
        ),
        (
            _("Navigation Visibility"),
            {
                "fields": [
                    "show_tickets_in_nav",
                    "show_video_in_nav",
                    "tickets_nav_label",
                ],
                "description": _(
                    "Extends the label customisation from issue #2482 with "
                    "full show/hide control over each nav item."
                ),
            },
        ),
        (
            _("MC Assignment"),
            {
                "fields": [
                    "mc_notifications_enabled",
                    "mc_permission_level",
                ],
            },
        ),
    ]


@admin.register(MCAssignment)
class MCAssignmentAdmin(admin.ModelAdmin):
    """
    MC assignment management.

    Creating a new assignment via the admin triggers the same notification
    path as the API — save_model() calls notify_mc_assigned() on first save.
    Updates to an existing assignment do not re-send the email to avoid
    spamming the MC every time an organiser edits the record.
    """

    list_display = [
        "event",
        "session_title",
        "team_member",
        "assigned_at",
        "notified",
    ]
    list_filter = ["event", "notified"]
    search_fields = ["session_title", "team_member__user__email"]
    readonly_fields = ["assigned_at", "notified"]

    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None
        super().save_model(request, obj, form, change)
        if not is_new:
            return
        try:
            settings = obj.event.integration_settings
        except IntegrationSettings.DoesNotExist:
            return
        if settings.mc_notifications_enabled:
            from .notifications import notify_mc_assigned  # noqa: PLC0415
            notify_mc_assigned(assignment=obj)


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    """
    Read-only audit trail for all sync operations.

    No adds, no edits, no deletes.  Organisers can search and filter but
    cannot tamper with the log.  The coloured level badge makes it easy
    to spot errors at a glance without opening individual records.
    """

    list_display = [
        "timestamp",
        "coloured_level",
        "action",
        "short_message",
    ]
    list_filter = ["level", "event"]
    search_fields = ["action", "message"]
    # Newest events first is more useful for troubleshooting.
    ordering = ["-timestamp"]

    def coloured_level(self, obj: SyncLog) -> str:
        colour = _LEVEL_COLOURS.get(obj.level, "#555")
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            colour,
            obj.get_level_display(),
        )

    coloured_level.short_description = _("Level")
    coloured_level.admin_order_field = "level"

    def short_message(self, obj: SyncLog) -> str:
        if len(obj.message) <= 80:
            return obj.message
        return obj.message[:77] + "…"

    short_message.short_description = _("Message")

    # ── Lockdown: nothing in this admin is writable. ──

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
