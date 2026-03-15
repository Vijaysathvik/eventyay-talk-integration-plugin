/**
 * usePluginSync.js — Vue 3 Composition API composable
 * =====================================================
 * Encapsulates all Talk↔Video sync state and operations.
 * Used by the PluginAdminPanel and SyncLog components.
 *
 * Demonstrates:
 *  - Vue 3 Composition API (ref, computed, watch)
 *  - Async API integration with loading/error states
 *  - Reactive state shared across components via composable
 */

import { ref, computed, watch } from 'vue'

const BASE_URL = '/api/v1/plugin/integration'

/**
 * Shared singleton state — all components that call usePluginSync()
 * share the same reactive state. This is the Pinia-lite pattern
 * (or use Pinia store in the full implementation).
 */
const sessions = ref([])
const speakers = ref([])
const syncLog = ref([])
const isSyncing = ref(false)
const lastSyncAt = ref(null)
const error = ref(null)

export function usePluginSync(eventSlug) {

  // ── Computed ──
  const liveSessions = computed(() =>
    sessions.value.filter(s => s.status === 'live')
  )

  const syncedRooms = computed(() =>
    sessions.value.filter(s => s.video_room_id != null).length
  )

  // ── Actions ──

  /**
   * Fetch all Talk sessions for this event from the plugin's
   * speaker API bridge endpoint (fixes Suhail's unfinished PR #1123).
   */
  async function loadSessions() {
    try {
      const res = await fetch(`${BASE_URL}/${eventSlug}/sessions/`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      sessions.value = await res.json()
    } catch (e) {
      error.value = `Failed to load sessions: ${e.message}`
    }
  }

  /**
   * Trigger a full sync of all Talk sessions → Video rooms.
   * Calls the plugin's sync endpoint which runs sync.py on the server.
   */
  async function triggerFullSync() {
    isSyncing.value = true
    error.value = null
    try {
      const res = await fetch(`${BASE_URL}/${eventSlug}/sync/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
      })
      const data = await res.json()
      syncLog.value.push(...data.log_entries)
      lastSyncAt.value = new Date().toISOString()
      await loadSessions()  // refresh after sync
    } catch (e) {
      error.value = `Sync failed: ${e.message}`
    } finally {
      isSyncing.value = false
    }
  }

  /**
   * Toggle a plugin integration on/off for this event.
   * PATCH to IntegrationSettings endpoint.
   */
  async function toggleIntegration(settingKey, value) {
    try {
      const res = await fetch(`${BASE_URL}/${eventSlug}/settings/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ [settingKey]: value }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      syncLog.value.push({
        timestamp: new Date().toISOString(),
        level: 'info',
        message: `Setting '${settingKey}' set to ${value}`,
      })
    } catch (e) {
      error.value = `Failed to update setting: ${e.message}`
    }
  }

  // ── Watch: auto-reload when event changes ──
  watch(() => eventSlug, () => {
    sessions.value = []
    syncLog.value = []
    loadSessions()
  }, { immediate: true })

  return {
    // state
    sessions, speakers, syncLog, isSyncing, lastSyncAt, error,
    // computed
    liveSessions, syncedRooms,
    // actions
    loadSessions, triggerFullSync, toggleIntegration,
  }
}

function getCsrfToken() {
  return document.cookie
    .split(';')
    .find(c => c.trim().startsWith('csrftoken='))
    ?.split('=')[1] ?? ''
}
