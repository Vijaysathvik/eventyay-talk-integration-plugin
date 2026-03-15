# eventyay Integration Plugin — GSoC 2026 Showcase

> **Project:** Implement eventyay features as a plugin in eventyay-talk (Project #3)
> **Proposal:** FOSSASIA GSoC 2026
> **Author:** Vijaysathvik

This repository demonstrates the plugin architecture, Vue 3 skills, and
Django integration knowledge required for Project #3. It is a working
prototype of the integration plugin described in the GSoC idea.

---

## What this proves

### 1. Plugin architecture (Django side)

The plugin is a **self-contained Django app** that registers with eventyay's
plugin system via `apps.py`. It connects to the rest of the system
**exclusively through Django signals** — it never imports from or modifies
core Talk, Tickets, or Video code.

```
eventyay_integration/
├── apps.py          ← Plugin entry point, registered via INSTALLED_APPS
├── signals.py       ← All sync logic triggered here via Django signals
├── sync.py          ← Cross-component data movement (Talk → Video)
├── models.py        ← IntegrationSettings (per-event config), MCAssignment
├── admin.py         ← Django admin UI for organiser configuration
└── api/
    └── endpoints.py ← REST API consumed by the Vue frontend
```

**Install:** `pip install -e .` then add `eventyay_integration` to `INSTALLED_APPS`.
**Disable:** Remove from `INSTALLED_APPS`. Zero core changes needed.

This is exactly the "modular, admin-manageable plugin" described in the proposal.

---

### 2. Vue 3 Composition API

`frontend/src/components/PluginAdminPanel.vue` demonstrates:

- `<script setup>` syntax (Vue 3 Composition API)
- `storeToRefs` for reactive Pinia store destructuring
- Composable pattern via `usePluginSync()` (shared reactive state)
- `v-model` bindings on plugin config toggles
- Async `onMounted` for settings load
- Conditional rendering with `v-if` / `v-show`
- Component slots for configurable UI sections

---

### 3. Pinia state management

`frontend/src/stores/pluginStore.js` shows:

- `defineStore` with Composition API syntax
- Computed getters (`activeIntegrations`, `navItems`)
- Async actions (`saveSettings`, `loadSettings`, `assignMC`)
- `isDirty` tracking for unsaved changes UX

---

### 4. API integration

`frontend/src/composables/usePluginSync.js` shows:

- `fetch` with CSRF token handling (Django pattern)
- Reactive `isSyncing` / `error` loading states
- `watch` on event slug for data refresh
- Clean separation of API layer from component logic

---

## Connection to existing PRs

| PR | What it does | How this plugin extends it |
|----|-------------|---------------------------|
| #2755 | Talk-only team auto-sync (my PR) | `signals.py` `on_team_saved` is the extracted, generalized version |
| #2356 | Ticket scoping fix (my PR, merged) | Plugin uses the corrected `OrderPosition` scoping in ticket gate check |
| #2482 | Nav label customization (SxxAq) | `models.py` adds `show_tickets_in_nav` bool fields — the missing show/hide layer |
| Suhail #1123 | Speaker API (unfinished, 2025) | `sync.py` `_inject_speaker_profile` builds on that endpoint pattern |

---

## Signal flow diagram

```
Talk session saved
       │
       ▼ (Django signal: post_save)
 eventyay_integration/signals.py
       │
       ├─── sync.sync_session_to_video_room()
       │         ├── VideoRoom.objects.get_or_create()
       │         └── _inject_speaker_profile()
       │
       └─── (if ticket_gate_enabled)
            tickets.validate_access()

New event created
       │
       ▼ (Django signal: post_save on Event)
 eventyay_integration/signals.py
       │
       └─── sync.add_event_to_talk_only_teams()
                └── team.limit_events.add(event)
                    (logic from PR #2755)
```

---

## Running the demo UI

The interactive admin panel demo (pure HTML/Vue 3 via CDN, no build step):

```bash
open demo/index.html
```

Or view hosted version: [GitHub Pages link]

---

## What the full GSoC project adds

This prototype covers the architecture. The 175-hour GSoC project would add:

1. **Migrations** — `IntegrationSettings` and `MCAssignment` database tables
2. **Full API endpoints** — DRF ViewSets for all plugin resources
3. **Tests** — Unit tests for each signal handler and sync function
4. **Template tags** — `{% plugin_nav_items %}` for the frontend nav
5. **Celery tasks** — Periodic sync task for `video_sync_mode = 'periodic'`
6. **MC notification emails** — Django email templates for MC assignment
7. **Documentation** — Setup guide, admin user guide, architecture docs
