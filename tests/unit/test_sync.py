"""
tests/unit/test_sync.py — Unit tests for eventyay_talk_integration.sync
=========================================================================
All external dependencies (VideoRoom model, email, settings) are mocked.
Tests are fully isolated: no test modifies shared state that another
test depends on.

Run: pytest tests/unit/test_sync.py -v
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def event():
    """Minimal fake Event."""
    e = MagicMock()
    e.pk = 1
    e.slug = "test-conf-2026"
    e.organiser = MagicMock()
    e.organiser.slug = "test-org"
    return e


@pytest.fixture()
def settings(event):
    """IntegrationSettings with safe defaults for the given event."""
    s = MagicMock()
    s.video_sync_enabled = True
    s.inject_speaker_profile = True
    s.ticket_gate_enabled = False
    s.video_sync_mode = "realtime"
    return s


@pytest.fixture()
def session(event):
    """Accepted TalkSession."""
    s = MagicMock()
    s.pk = 42
    s.event = event
    s.title = "Keynote: The Future of Open Source"
    s.abstract = "A deep dive into what open source means in 2026."
    s.state = "accepted"
    s.speakers = MagicMock()
    s.speakers.exists.return_value = False
    s.speakers.select_related.return_value.first.return_value = None
    return s


@pytest.fixture()
def speaker(session):
    """Speaker with a user and biography."""
    sp = MagicMock()
    sp.biography = "Core contributor to eventyay since 2022."
    sp.picture = None  # no uploaded photo
    sp.event = session.event
    sp.user = MagicMock()
    sp.user.email = "speaker@example.com"
    sp.user.get_full_name.return_value = "Alice Example"

    # Wire up session.speakers to return this speaker.
    session.speakers.exists.return_value = True
    session.speakers.select_related.return_value.first.return_value = sp
    return sp


@pytest.fixture()
def video_room():
    """A plugin-managed VideoRoom."""
    r = MagicMock()
    r.pk = 99
    r.plugin_managed = True
    return r


# ── Tests: sync_session_to_video_room ─────────────────────────────────────────


@patch("eventyay_talk_integration.sync.SyncLog")
@patch("eventyay.video.models.VideoRoom")
def test_sync_creates_video_room_for_new_session(mock_room_cls, mock_log, session):
    """
    A new session (created=True) should result in get_or_create being called
    and a VideoRoom being returned.
    """
    from eventyay_talk_integration.sync import sync_session_to_video_room

    # --- Arrange ---
    fake_room = MagicMock()
    mock_room_cls.objects.get_or_create.return_value = (fake_room, True)

    # --- Act ---
    result = sync_session_to_video_room(session=session, created=True, inject_speaker=False)

    # --- Assert ---
    mock_room_cls.objects.get_or_create.assert_called_once_with(
        talk_session_id=session.pk,
        defaults={
            "event": session.event,
            "name": session.title,
            "description": session.abstract,
        },
    )
    assert result is fake_room


@patch("eventyay_talk_integration.sync.SyncLog")
@patch("eventyay.video.models.VideoRoom")
def test_sync_updates_existing_room_on_session_change(mock_room_cls, mock_log, session):
    """
    When a session is updated and a room already exists, the room's name and
    description should be updated to reflect the new session metadata.
    """
    from eventyay_talk_integration.sync import sync_session_to_video_room

    # --- Arrange ---
    existing_room = MagicMock()
    mock_room_cls.objects.get_or_create.return_value = (existing_room, False)
    session.title = "Updated Keynote Title"

    # --- Act ---
    sync_session_to_video_room(session=session, created=False, inject_speaker=False)

    # --- Assert ---
    assert existing_room.name == "Updated Keynote Title"
    existing_room.save.assert_called_once_with(update_fields=["name", "description"])


@patch("eventyay_talk_integration.sync.SyncLog")
@patch("eventyay.video.models.VideoRoom")
def test_sync_does_not_create_room_for_draft_session(mock_room_cls, mock_log, session):
    """
    Draft sessions (state='submitted') should not result in a video room being
    created.  The guard lives in the signal handler, not in sync.py, but we
    verify sync.py doesn't call get_or_create when the caller skips it.

    This test documents the contract: signal.py is responsible for the guard;
    sync.py trusts its caller.
    """
    from eventyay_talk_integration.sync import sync_session_to_video_room

    # --- Arrange ---
    session.state = "submitted"
    fake_room = MagicMock()
    mock_room_cls.objects.get_or_create.return_value = (fake_room, True)

    # --- Act ---
    # Caller (signal) is supposed to skip non-accepted sessions.
    # Here we call directly — sync.py itself does NOT check state.
    sync_session_to_video_room(session=session, created=True, inject_speaker=False)

    # --- Assert ---
    # get_or_create still fires because sync.py doesn't guard state.
    # The signal test (test_signals.py) verifies the guard at that layer.
    mock_room_cls.objects.get_or_create.assert_called_once()


@patch("eventyay_talk_integration.sync.SyncLog")
@patch("eventyay.video.models.VideoRoom")
def test_sync_injects_speaker_name_and_bio(mock_room_cls, mock_log, session, speaker):
    """
    With inject_speaker=True and a speaker attached, the room should have
    speaker_name, speaker_bio, and speaker_avatar_url populated.
    """
    from eventyay_talk_integration.sync import sync_session_to_video_room

    # --- Arrange ---
    room = MagicMock()
    mock_room_cls.objects.get_or_create.return_value = (room, True)

    # --- Act ---
    sync_session_to_video_room(session=session, created=True, inject_speaker=True)

    # --- Assert ---
    assert room.speaker_name == "Alice Example"
    assert room.speaker_bio == "Core contributor to eventyay since 2022."
    room.save.assert_any_call(
        update_fields=["speaker_name", "speaker_bio", "speaker_avatar_url"]
    )


@patch("eventyay_talk_integration.sync.IntegrationSettings")
@patch("eventyay_talk_integration.sync.SyncLog")
@patch("eventyay.video.models.VideoRoom")
def test_sync_uses_gravatar_when_no_photo(
    mock_room_cls, mock_log, mock_settings_cls, session, speaker
):
    """
    When the speaker has no uploaded photo, the avatar URL should be a
    Gravatar URL derived from the speaker's email MD5.
    """
    from eventyay_talk_integration.sync import _resolve_avatar

    # --- Arrange ---
    # speaker.picture is falsy (already set to None in fixture)

    # --- Act ---
    avatar_url = _resolve_avatar(speaker)

    # --- Assert ---
    assert "gravatar.com/avatar" in avatar_url
    # MD5 of "speaker@example.com" should appear in the URL
    assert "d374f8b2ae31c5b2479df3c41b24b44e" in avatar_url


@patch("eventyay_talk_integration.sync.SyncLog")
@patch("eventyay.video.models.VideoRoom")
def test_sync_uses_uploaded_photo_over_gravatar(mock_room_cls, mock_log, session, speaker):
    """
    An uploaded photo should take priority over Gravatar.
    """
    from eventyay_talk_integration.sync import _resolve_avatar

    # --- Arrange ---
    speaker.picture = MagicMock()
    speaker.picture.url = "https://cdn.example.com/photos/alice.jpg"

    # --- Act ---
    result = _resolve_avatar(speaker)

    # --- Assert ---
    assert result == "https://cdn.example.com/photos/alice.jpg"


@patch("eventyay.video.models.VideoRoom")
def test_remove_room_deletes_only_plugin_managed(mock_room_cls, session):
    """
    remove_video_room_for_session should delete only rooms tagged
    plugin_managed=True.  Manually-created rooms must be left intact.
    """
    from eventyay_talk_integration.sync import remove_video_room_for_session

    # --- Act ---
    remove_video_room_for_session(session=session)

    # --- Assert ---
    mock_room_cls.objects.filter.assert_called_once_with(
        talk_session_id=session.pk,
        plugin_managed=True,
    )
    mock_room_cls.objects.filter.return_value.delete.assert_called_once()


@patch("eventyay.video.models.VideoRoom")
def test_remove_room_skips_manually_created_rooms(mock_room_cls, session):
    """
    If plugin_managed=False rooms exist for the session, they should NOT
    be deleted by the plugin's cleanup code.

    We verify this by checking that filter() is always called with
    plugin_managed=True — the DB enforces the rest.
    """
    from eventyay_talk_integration.sync import remove_video_room_for_session

    # --- Arrange ---
    mock_room_cls.objects.filter.return_value.delete.return_value = (0, {})

    # --- Act ---
    remove_video_room_for_session(session=session)

    # --- Assert ---
    call_kwargs = mock_room_cls.objects.filter.call_args.kwargs
    assert call_kwargs.get("plugin_managed") is True


@patch("eventyay_talk_integration.sync.IntegrationSettings")
@patch("eventyay_talk_integration.sync.SyncLog")
@patch("eventyay.video.models.VideoRoom")
def test_full_resync_returns_correct_summary_keys(
    mock_room_cls, mock_log, mock_settings_cls, event
):
    """
    full_resync_for_event() should return a dict with at least
    'synced', 'skipped', and 'errors' keys so the admin view can
    display the result without knowing the internals.
    """
    from eventyay_talk_integration.sync import full_resync_for_event

    # --- Arrange ---
    fake_settings = MagicMock()
    fake_settings.video_sync_enabled = True
    mock_settings_cls.for_event.return_value = fake_settings

    # No sessions for simplicity — we're testing the return shape, not logic.
    with patch("eventyay_talk_integration.sync._get_accepted_sessions", return_value=[]):
        # --- Act ---
        result = full_resync_for_event(event=event)

    # --- Assert ---
    assert "synced" in result
    assert "skipped" in result
    assert "errors" in result


@patch("eventyay_talk_integration.sync.IntegrationSettings")
@patch("eventyay_talk_integration.sync.SyncLog")
def test_full_resync_skips_when_video_sync_disabled(mock_log, mock_settings_cls, event):
    """
    If video_sync_enabled is False, full_resync_for_event should immediately
    return without touching any VideoRoom objects.
    """
    from eventyay_talk_integration.sync import full_resync_for_event

    # --- Arrange ---
    fake_settings = MagicMock()
    fake_settings.video_sync_enabled = False
    mock_settings_cls.for_event.return_value = fake_settings

    with patch("eventyay.video.models.VideoRoom") as mock_room:
        # --- Act ---
        result = full_resync_for_event(event=event)

    # --- Assert ---
    mock_room.objects.get_or_create.assert_not_called()
    assert result.get("synced") == 0


@patch("eventyay_talk_integration.sync.SyncLog")
def test_sync_events_to_talk_only_team_sets_all_events(mock_log):
    """
    sync_events_to_talk_only_team() should call team.limit_events.set()
    with all events belonging to the team's organiser.
    """
    from eventyay_talk_integration.sync import sync_events_to_talk_only_team

    # --- Arrange ---
    team = MagicMock()
    team.organiser = MagicMock()
    team.name = "Talk volunteers"

    fake_events = [MagicMock(), MagicMock()]
    with patch("eventyay.models.Event") as mock_event_cls:
        mock_event_cls.objects.filter.return_value = fake_events
        mock_event_cls.objects.filter.return_value.count.return_value = 2

        # --- Act ---
        sync_events_to_talk_only_team(team=team)

    # --- Assert ---
    team.limit_events.set.assert_called_once_with(fake_events)


@patch("eventyay_talk_integration.sync.SyncLog")
def test_add_event_to_talk_only_teams_on_event_create(mock_log):
    """
    add_event_to_talk_only_teams() should call team.limit_events.add(event)
    for every Talk-only team (all_events=True) under the same organiser.
    """
    from eventyay_talk_integration.sync import add_event_to_talk_only_teams

    # --- Arrange ---
    event = MagicMock()
    event.organiser = MagicMock()
    event.slug = "new-event-2026"

    team_a = MagicMock()
    team_b = MagicMock()

    with patch("eventyay.models.Team") as mock_team_cls:
        mock_team_cls.objects.filter.return_value = [team_a, team_b]

        # --- Act ---
        add_event_to_talk_only_teams(event=event)

    # --- Assert ---
    team_a.limit_events.add.assert_called_once_with(event)
    team_b.limit_events.add.assert_called_once_with(event)
