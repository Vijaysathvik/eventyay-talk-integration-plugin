"""
sync.py — Cross-component sync logic
======================================
All data movement between Talk, Tickets, and Video lives here.
Functions are called by signal handlers in signals.py.
Nothing in this file imports from core at module level.
"""

import logging

logger = logging.getLogger(__name__)


def sync_session_to_video_room(session, created: bool, inject_speaker: bool):
    """
    Creates or updates a video room to match a Talk session.

    On create: provisions a new video room via the Video API,
               stores the room_id back on the session for future updates.
    On update: patches the room metadata (title, description, schedule).
    If inject_speaker=True: fetches the speaker profile and pushes it
                             to the room's metadata endpoint.
    """
    from eventyay.video.models import VideoRoom  # lazy import — no circular dep
    from .models import MCAssignment

    room, room_created = VideoRoom.objects.get_or_create(
        talk_session_id=session.pk,
        defaults={
            "event": session.event,
            "name": session.title,
            "description": session.abstract or "",
        },
    )

    if not room_created:
        # Update existing room metadata to reflect Talk changes
        room.name = session.title
        room.description = session.abstract or ""
        room.save(update_fields=["name", "description"])

    if inject_speaker and session.speakers.exists():
        _inject_speaker_profile(room=room, session=session)

    action = "created" if room_created else "updated"
    logger.info(
        "plugin:sync — video room %s for session '%s' (event: %s)",
        action, session.title, session.event.slug,
    )
    return room


def remove_video_room_for_session(session):
    """
    Removes the video room that was auto-created for a deleted Talk session.
    Does nothing if the room was created manually (plugin_managed=False).
    """
    from eventyay.video.models import VideoRoom

    VideoRoom.objects.filter(
        talk_session_id=session.pk,
        plugin_managed=True,
    ).delete()

    logger.info("plugin:sync — removed video room for deleted session '%s'", session.title)


def _inject_speaker_profile(room, session):
    """
    Pushes the first speaker's profile data into the video room metadata.
    This is what surfaces speaker bios/photos inside the video component.
    Speaker API bridge — connects to PR #1123 (Suhail's unfinished work).
    """
    speaker = session.speakers.select_related("user").first()
    if not speaker:
        return

    room.speaker_name = speaker.user.get_full_name()
    room.speaker_bio = getattr(speaker, "biography", "")
    room.speaker_avatar_url = _get_speaker_avatar(speaker)
    room.save(update_fields=["speaker_name", "speaker_bio", "speaker_avatar_url"])


def _get_speaker_avatar(speaker):
    """Return speaker photo URL, falling back to Gravatar if configured."""
    if speaker.picture:
        return speaker.picture.url
    from .models import IntegrationSettings
    settings = IntegrationSettings.for_event(speaker.event)
    if settings.inject_speaker_profile:
        import hashlib
        email = (speaker.user.email or "").strip().lower()
        h = hashlib.md5(email.encode()).hexdigest()
        return f"https://www.gravatar.com/avatar/{h}?d=identicon"
    return ""


def sync_events_to_talk_only_team(team):
    """
    Given a Talk-only team (all_events=True), add all organiser events to it.
    This implements the post_migrate signal logic from PR #2755 at runtime.
    """
    from eventyay.models import Event

    events = Event.objects.filter(organiser=team.organiser)
    team.limit_events.set(events)
    logger.info(
        "plugin:sync — synced %d events to Talk-only team '%s'",
        events.count(), team.name,
    )


def add_event_to_talk_only_teams(event):
    """
    When a new event is created, add it to all Talk-only teams
    under the same organiser.
    """
    from eventyay.models import Team

    talk_only_teams = Team.objects.filter(
        organiser=event.organiser,
        all_events=True,
    )
    for team in talk_only_teams:
        team.limit_events.add(event)

    logger.info(
        "plugin:sync — added new event '%s' to %d Talk-only teams",
        event.slug, talk_only_teams.count(),
    )
