"""
signals.py — Plugin sync layer
================================
All Talk↔Tickets↔Video synchronization is driven by Django signals.
This keeps integration logic OUT of core components — Talk doesn't
know about Video; Video doesn't know about Tickets.
The plugin listens and bridges them here.

Signal flow:
  Talk session created  →  post_save on TalkSession
                        →  plugin creates/updates VideoRoom
                        →  plugin pushes speaker profile to VideoRoom
                        →  plugin enforces ticket gate if enabled

  Team created as Talk-only  →  post_save on Team
                              →  plugin auto-syncs all events to team
                              (this is what PR #2755 implements)
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

# We import lazily inside handlers to avoid circular imports at startup.
# The plugin must never import from core modules at module level.


@receiver(post_save, sender="eventyay_talk.TalkSession")
def on_talk_session_saved(sender, instance, created, **kwargs):
    """
    When a Talk session is created or updated, sync it to the video component.
    Creates a VideoRoom if one doesn't exist yet (auto-create setting must be on).
    Injects speaker profile metadata into the room.
    """
    from .sync import sync_session_to_video_room
    from .models import IntegrationSettings

    settings = IntegrationSettings.for_event(instance.event)

    if not settings.video_sync_enabled:
        return

    sync_session_to_video_room(
        session=instance,
        created=created,
        inject_speaker=settings.inject_speaker_profile,
    )


@receiver(post_delete, sender="eventyay_talk.TalkSession")
def on_talk_session_deleted(sender, instance, **kwargs):
    """
    When a Talk session is deleted, remove the associated video room
    (only if it was auto-created by this plugin).
    """
    from .sync import remove_video_room_for_session

    remove_video_room_for_session(session=instance)


@receiver(post_save, sender="eventyay.Team")
def on_team_saved(sender, instance, created, **kwargs):
    """
    When a Talk-only team is created, automatically sync all existing
    events to that team so they appear on the Talk dashboard.

    This is the core logic from PR #2755 — extracted into a signal
    so it runs automatically without any core Team model changes.
    """
    if not instance.all_events:
        # Only Talk-only teams (all_events=True) need auto-sync
        return

    from .sync import sync_events_to_talk_only_team

    sync_events_to_talk_only_team(team=instance)


@receiver(post_save, sender="eventyay.Event")
def on_event_created(sender, instance, created, **kwargs):
    """
    When a new event is created, find all Talk-only teams under
    the same organiser and add the event to them automatically.

    This prevents Talk-only teams from missing new events.
    (Also from PR #2755 — the post_migrate hook equivalent for runtime.)
    """
    if not created:
        return

    from .sync import add_event_to_talk_only_teams

    add_event_to_talk_only_teams(event=instance)
