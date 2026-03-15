"""
eventyay_integration - Plugin entry point
=========================================
This Django app registers itself with eventyay's plugin system.
It is completely decoupled from core Talk, Tickets, and Video code —
all integration logic lives here, never in core modules.

To install: add 'eventyay_integration' to INSTALLED_APPS in settings.
To disable: remove from INSTALLED_APPS. Zero core code changes needed.
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class EvenYayIntegrationConfig(AppConfig):
    name = "eventyay_integration"
    verbose_name = _("eventyay Integration Plugin")

    # ── Plugin metadata (read by eventyay plugin registry) ──
    # These are surfaced in the admin plugin management UI
    plugin_name = _("eventyay Integration Plugin")
    plugin_author = "Vijaysathvik"
    plugin_description = _(
        "Connects Talk, Tickets, and Video components via a modular admin plugin. "
        "Provides session sync, speaker profiles in video rooms, ticket access gating, "
        "and MC assignment — without modifying any core eventyay code."
    )
    plugin_visible = True

    def ready(self):
        """
        Called once Django has finished loading all apps.
        Register all signal handlers here so the plugin
        responds to Talk/Tickets/Video events automatically.
        """
        from . import signals  # noqa: F401 — import triggers signal registration
