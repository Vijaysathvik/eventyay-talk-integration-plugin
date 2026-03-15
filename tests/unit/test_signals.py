"""
tests/unit/test_signals.py — Unit tests for eventyay_talk_integration.signals
===============================================================================
Signal handlers are tested by calling them directly rather than firing the
actual Django signal, because:
  1. It avoids needing the full eventyay model setup in CI.
  2. It lets us test the exact guard conditions without side effects.

All sync functions and notification helpers are mocked; we test signal
routing logic, not the underlying sync operations (those live in test_sync.py).
"""

from unittest.mock import MagicMock, call, patch

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_event(plugin_active: bool = True) -> MagicMock:
    """Return a fake event whose plugins string includes/excludes our label."""
    event = MagicMock()
    event.slug = "test-event"
    if plugin_active:
        event.plugins = "some_other_plugin,eventyay_talk_integration,another"
    else:
        event.plugins = "some_other_plugin,another"
    return event


def _make_session(event, state: str = "accepted") -> MagicMock:
    session = MagicMock()
    session.event = event
    session.state = state
    session.pk = 7
    session.title = "Test session"
    return session


# ── Tests: on_talk_session_saved ───────────────────────────────────────────────


@patch("eventyay_talk_integration.signals.IntegrationSettings")
@patch("eventyay_talk_integration.signals.sync_session_to_video_room")
def test_session_signal_skips_when_plugin_not_active(mock_sync, mock_settings_cls):
    """
    If 'eventyay_talk_integration' is not in event.plugins, the signal handler
    must return without calling sync_session_to_video_room.
    """
    from eventyay_talk_integration.signals import on_talk_session_saved

    # --- Arrange ---
    event = _make_event(plugin_active=False)
    session = _make_session(event)

    # --- Act ---
    on_talk_session_saved(sender=None, instance=session, created=True)

    # --- Assert ---
    mock_sync.assert_not_called()


@patch("eventyay_talk_integration.signals.IntegrationSettings")
@patch("eventyay_talk_integration.signals.sync_session_to_video_room")
def test_session_signal_skips_when_video_sync_disabled(mock_sync, mock_settings_cls):
    """
    If IntegrationSettings.video_sync_enabled is False, sync should not fire
    even if the plugin is active.
    """
    from eventyay_talk_integration.signals import on_talk_session_saved

    # --- Arrange ---
    event = _make_event(plugin_active=True)
    session = _make_session(event)

    fake_settings = MagicMock()
    fake_settings.video_sync_enabled = False
    mock_settings_cls.for_event.return_value = fake_settings

    # --- Act ---
    on_talk_session_saved(sender=None, instance=session, created=True)

    # --- Assert ---
    mock_sync.assert_not_called()


@patch("eventyay_talk_integration.signals.IntegrationSettings")
@patch("eventyay_talk_integration.signals.sync_session_to_video_room")
def test_session_signal_skips_draft_state(mock_sync, mock_settings_cls):
    """
    Sessions in 'submitted' state should not trigger a sync.  Only sessions
    with state='accepted' are synced to video rooms.
    """
    from eventyay_talk_integration.signals import on_talk_session_saved

    # --- Arrange ---
    event = _make_event(plugin_active=True)
    session = _make_session(event, state="submitted")

    fake_settings = MagicMock()
    fake_settings.video_sync_enabled = True
    mock_settings_cls.for_event.return_value = fake_settings

    # --- Act ---
    on_talk_session_saved(sender=None, instance=session, created=True)

    # --- Assert ---
    mock_sync.assert_not_called()


@patch("eventyay_talk_integration.signals.remove_video_room_for_session")
def test_session_signal_skips_deleted_session_without_managed_room(mock_remove):
    """
    on_talk_session_deleted should call remove_video_room_for_session and
    not raise even when no plugin-managed room exists (the sync function
    handles that case internally).
    """
    from eventyay_talk_integration.signals import on_talk_session_deleted

    # --- Arrange ---
    event = _make_event(plugin_active=True)
    session = _make_session(event)
    mock_remove.return_value = None  # 0 rooms deleted — no error

    # --- Act ---
    on_talk_session_deleted(sender=None, instance=session)

    # --- Assert ---
    mock_remove.assert_called_once_with(session=session)


# ── Tests: on_team_saved ───────────────────────────────────────────────────────


@patch("eventyay_talk_integration.signals.sync_events_to_talk_only_team")
def test_team_signal_only_fires_for_all_events_teams(mock_sync):
    """
    on_team_saved should only call sync_events_to_talk_only_team when
    team.all_events=True.  For regular scoped teams, nothing should happen.
    """
    from eventyay_talk_integration.signals import on_team_saved

    # --- Arrange ---
    scoped_team = MagicMock()
    scoped_team.all_events = False

    # --- Act ---
    on_team_saved(sender=None, instance=scoped_team, created=True)

    # --- Assert ---
    mock_sync.assert_not_called()


# ── Tests: MC assignment signal ────────────────────────────────────────────────


@patch("eventyay_talk_integration.signals.notify_mc_assigned")
@patch("eventyay_talk_integration.signals.IntegrationSettings")
def test_mc_signal_sends_notification_on_create(mock_settings_cls, mock_notify):
    """
    When an MCAssignment is created for the first time (created=True) and
    mc_notifications_enabled=True, notify_mc_assigned should be called once.
    """
    from eventyay_talk_integration.signals import on_mc_assigned

    # --- Arrange ---
    event = _make_event(plugin_active=True)
    assignment = MagicMock()
    assignment.event = event

    fake_settings = MagicMock()
    fake_settings.mc_notifications_enabled = True
    mock_settings_cls.for_event.return_value = fake_settings

    # --- Act ---
    on_mc_assigned(sender=None, instance=assignment, created=True)

    # --- Assert ---
    mock_notify.assert_called_once_with(assignment=assignment)


@patch("eventyay_talk_integration.signals.notify_mc_assigned")
@patch("eventyay_talk_integration.signals.IntegrationSettings")
def test_mc_signal_skips_notification_on_update(mock_settings_cls, mock_notify):
    """
    When an existing MCAssignment is saved (created=False), no notification
    should be sent — we don't want to spam the MC on every edit.
    """
    from eventyay_talk_integration.signals import on_mc_assigned

    # --- Arrange ---
    event = _make_event(plugin_active=True)
    assignment = MagicMock()
    assignment.event = event

    fake_settings = MagicMock()
    fake_settings.mc_notifications_enabled = True
    mock_settings_cls.for_event.return_value = fake_settings

    # --- Act ---
    on_mc_assigned(sender=None, instance=assignment, created=False)

    # --- Assert ---
    mock_notify.assert_not_called()


@patch("eventyay_talk_integration.signals.notify_mc_assigned")
@patch("eventyay_talk_integration.signals.IntegrationSettings")
def test_mc_signal_skips_when_notifications_disabled(mock_settings_cls, mock_notify):
    """
    Even on a new MCAssignment, if mc_notifications_enabled=False the signal
    should not send the email.
    """
    from eventyay_talk_integration.signals import on_mc_assigned

    # --- Arrange ---
    event = _make_event(plugin_active=True)
    assignment = MagicMock()
    assignment.event = event

    fake_settings = MagicMock()
    fake_settings.mc_notifications_enabled = False
    mock_settings_cls.for_event.return_value = fake_settings

    # --- Act ---
    on_mc_assigned(sender=None, instance=assignment, created=True)

    # --- Assert ---
    mock_notify.assert_not_called()


# ── Tests: error isolation ─────────────────────────────────────────────────────


@patch("eventyay_talk_integration.signals.IntegrationSettings")
@patch("eventyay_talk_integration.signals.sync_session_to_video_room")
def test_signal_failure_does_not_propagate(mock_sync, mock_settings_cls):
    """
    If sync_session_to_video_room raises an exception, the signal handler
    must catch it and not re-raise.  A plugin failure must never bubble up
    to the core Talk save path and break session creation for the organiser.
    """
    from eventyay_talk_integration.signals import on_talk_session_saved

    # --- Arrange ---
    event = _make_event(plugin_active=True)
    session = _make_session(event, state="accepted")

    fake_settings = MagicMock()
    fake_settings.video_sync_enabled = True
    fake_settings.inject_speaker_profile = False
    mock_settings_cls.for_event.return_value = fake_settings

    mock_sync.side_effect = RuntimeError("Video API timed out")

    # --- Act & Assert ---
    # This should NOT raise.  If it does, the test (and therefore the plugin)
    # fails its isolation guarantee.
    try:
        on_talk_session_saved(sender=None, instance=session, created=True)
    except RuntimeError:
        pytest.fail(
            "on_talk_session_saved let a RuntimeError propagate to the caller. "
            "Plugin failures must be caught internally."
        )
