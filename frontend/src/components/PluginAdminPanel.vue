<template>
  <!--
    PluginAdminPanel.vue
    =====================
    The main admin interface for the eventyay integration plugin.
    Organisers configure Talk↔Tickets↔Video integrations here
    without touching any core code.

    Demonstrates:
      - Vue 3 <script setup> Composition API
      - Pinia store integration
      - Component composition (child components)
      - v-model on plugin config toggles
      - Async API calls with loading states
      - Conditional rendering based on plugin state
  -->
  <div class="plugin-admin">

    <!-- Header -->
    <div class="admin-header">
      <div class="admin-title">
        <h1>Integration Plugin</h1>
        <span class="event-slug">{{ eventSlug }}</span>
      </div>
      <div class="admin-actions">
        <button
          class="btn btn-secondary"
          :disabled="isSyncing"
          @click="handleSync"
        >
          <span v-if="isSyncing">Syncing…</span>
          <span v-else>↻ Sync now</span>
        </button>
        <button
          class="btn btn-primary"
          :disabled="!isDirty || isSaving"
          @click="handleSave"
        >
          {{ isSaving ? 'Saving…' : 'Save settings' }}
        </button>
      </div>
    </div>

    <!-- Error banner -->
    <div v-if="error" class="error-banner">
      {{ error }}
    </div>

    <!-- Stats row -->
    <div class="stats-row">
      <StatCard label="Talk sessions" :value="sessions.length" :sub="`${liveSessions.length} live`" />
      <StatCard label="Synced rooms" :value="syncedRooms" sub="Video rooms created" />
      <StatCard label="Active integrations" :value="activeIntegrations.length" sub="of 4 available" />
      <StatCard label="Last sync" :value="lastSyncAt ? formatTime(lastSyncAt) : 'Never'" />
    </div>

    <!-- Integration toggles -->
    <section class="section">
      <h2>Integrations</h2>
      <p class="section-desc">
        Toggle integrations on or off. Changes take effect immediately.
        No core eventyay code is modified — all logic lives in this plugin.
      </p>

      <IntegrationCard
        id="video_sync"
        icon="🎥"
        title="Talk → Video Sync"
        description="Auto-creates video rooms from Talk sessions. Pushes session title,
                     description, and speaker profile into each room."
        :enabled="settings.video_sync_enabled"
        @toggle="val => updateSetting('video_sync_enabled', val)"
      >
        <!-- Slot: extra config shown when enabled -->
        <template #config v-if="settings.video_sync_enabled">
          <ConfigRow label="Inject speaker profiles" help="Show speaker bio and photo in video room">
            <ToggleSwitch
              v-model="settings.inject_speaker_profile"
              @update:modelValue="val => updateSetting('inject_speaker_profile', val)"
            />
          </ConfigRow>
          <ConfigRow label="Sync mode" help="When Talk changes propagate to Video">
            <select v-model="settings.video_sync_mode" @change="isDirty = true">
              <option value="realtime">Real-time (on save)</option>
              <option value="periodic">Periodic (5 min)</option>
              <option value="manual">Manual only</option>
            </select>
          </ConfigRow>
        </template>
      </IntegrationCard>

      <IntegrationCard
        id="ticket_gate"
        icon="🎫"
        title="Ticket Access Gate"
        description="Requires a valid ticket purchase to join video rooms.
                     Validates against the Tickets component on join."
        :enabled="settings.ticket_gate_enabled"
        @toggle="val => updateSetting('ticket_gate_enabled', val)"
      />

      <IntegrationCard
        id="speaker_api"
        icon="👤"
        title="Speaker API Bridge"
        description="Exposes Talk speaker profiles via REST API so Video and
                     Tickets components can display speaker data cross-component."
        :enabled="settings.inject_speaker_profile"
        @toggle="val => updateSetting('inject_speaker_profile', val)"
      />

      <IntegrationCard
        id="mc_assignment"
        icon="🎙️"
        title="MC Assignment"
        description="Assign team members as MCs to video rooms with role-based
                     permissions and automatic email notifications."
        :enabled="settings.mc_notifications_enabled"
        @toggle="val => updateSetting('mc_notifications_enabled', val)"
      >
        <template #config v-if="settings.mc_notifications_enabled">
          <ConfigRow label="MC permission level" help="What assigned MCs can do in their rooms">
            <select v-model="settings.mc_permission_level" @change="isDirty = true">
              <option value="view">View only</option>
              <option value="moderate">Moderate (mute/kick)</option>
              <option value="host">Host (full control)</option>
            </select>
          </ConfigRow>
        </template>
      </IntegrationCard>
    </section>

    <!-- Navigation settings (issue #2482 extension) -->
    <section class="section">
      <h2>Navigation visibility</h2>
      <p class="section-desc">
        Control which components appear in the public event navigation.
        Extends label customization with full show/hide per component.
      </p>
      <ConfigRow label="Show Tickets in nav" help="Display Tickets link in public navigation">
        <ToggleSwitch
          v-model="settings.show_tickets_in_nav"
          @update:modelValue="val => updateSetting('show_tickets_in_nav', val)"
        />
      </ConfigRow>
      <ConfigRow label="Show Join Online Video" help="Display video join link in public navigation">
        <ToggleSwitch
          v-model="settings.show_video_in_nav"
          @update:modelValue="val => updateSetting('show_video_in_nav', val)"
        />
      </ConfigRow>
      <ConfigRow label="Custom Tickets label" help="Leave blank to use default 'Tickets'">
        <input
          v-model="settings.tickets_nav_label"
          type="text"
          placeholder="e.g. Buy tickets"
          @input="isDirty = true"
        />
      </ConfigRow>
    </section>

    <!-- Session list with sync status -->
    <section class="section">
      <h2>Sessions · sync status</h2>
      <SessionSyncTable :sessions="sessions" :settings="settings" />
    </section>

  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { usePluginStore } from '../stores/pluginStore'
import { usePluginSync } from '../composables/usePluginSync'

// ── Props ──
const props = defineProps({
  eventSlug: {
    type: String,
    required: true,
  },
})

// ── Store ──
const store = usePluginStore()
const { settings, isDirty, isSaving, activeIntegrations } = storeToRefs(store)
const { updateSetting, saveSettings, loadSettings } = store

// ── Sync composable ──
const {
  sessions, liveSessions, syncedRooms,
  isSyncing, lastSyncAt, error,
  triggerFullSync,
} = usePluginSync(props.eventSlug)

// ── Lifecycle ──
onMounted(async () => {
  await loadSettings(props.eventSlug)
})

// ── Handlers ──
async function handleSync() {
  await triggerFullSync()
}

async function handleSave() {
  await saveSettings(props.eventSlug)
}

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString('en-GB', {
    hour: '2-digit', minute: '2-digit',
  })
}
</script>
