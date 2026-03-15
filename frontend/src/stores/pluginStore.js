/**
 * pluginStore.js — Pinia store
 * ==============================
 * Manages plugin integration settings state.
 * Demonstrates Pinia usage (Vue 3 recommended state management),
 * which is one of the required skills for Project #2 and #3.
 *
 * In the full GSoC implementation this store would replace
 * the composable pattern for settings that need to be shared
 * across deeply nested components.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const usePluginStore = defineStore('plugin', () => {

  // ── State ──
  const settings = ref({
    video_sync_enabled: true,
    inject_speaker_profile: true,
    video_sync_mode: 'realtime',
    ticket_gate_enabled: false,
    show_tickets_in_nav: true,
    show_video_in_nav: true,
    tickets_nav_label: '',
    mc_notifications_enabled: true,
    mc_permission_level: 'moderate',
  })

  const mcAssignments = ref([])
  const isDirty = ref(false)
  const isSaving = ref(false)

  // ── Getters ──
  const activeIntegrations = computed(() => {
    const active = []
    if (settings.value.video_sync_enabled) active.push('video_sync')
    if (settings.value.ticket_gate_enabled) active.push('ticket_gate')
    if (settings.value.inject_speaker_profile) active.push('speaker_api')
    return active
  })

  const navItems = computed(() => {
    const items = []
    if (settings.value.show_tickets_in_nav) {
      items.push({
        key: 'tickets',
        label: settings.value.tickets_nav_label || 'Tickets',
        url: 'tickets/',
      })
    }
    if (settings.value.show_video_in_nav) {
      items.push({
        key: 'video',
        label: 'Join Online Video',
        url: 'video/',
      })
    }
    return items
  })

  // ── Actions ──
  function updateSetting(key, value) {
    settings.value[key] = value
    isDirty.value = true
  }

  async function saveSettings(eventSlug) {
    isSaving.value = true
    try {
      const res = await fetch(`/api/v1/plugin/integration/${eventSlug}/settings/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify(settings.value),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      isDirty.value = false
    } finally {
      isSaving.value = false
    }
  }

  async function loadSettings(eventSlug) {
    const res = await fetch(`/api/v1/plugin/integration/${eventSlug}/settings/`)
    if (res.ok) {
      settings.value = await res.json()
      isDirty.value = false
    }
  }

  async function assignMC({ eventSlug, videoRoomId, teamMemberId, sessionTitle }) {
    const res = await fetch(`/api/v1/plugin/integration/${eventSlug}/mc/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({
        video_room_id: videoRoomId,
        team_member_id: teamMemberId,
        session_title: sessionTitle,
      }),
    })
    if (res.ok) {
      const assignment = await res.json()
      mcAssignments.value.push(assignment)
    }
  }

  return {
    settings, mcAssignments, isDirty, isSaving,
    activeIntegrations, navItems,
    updateSetting, saveSettings, loadSettings, assignMC,
  }
})

function getCsrfToken() {
  return document.cookie
    .split(';')
    .find(c => c.trim().startsWith('csrftoken='))
    ?.split('=')[1] ?? ''
}
