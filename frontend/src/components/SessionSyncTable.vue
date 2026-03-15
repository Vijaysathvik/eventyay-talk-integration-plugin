<template>
  <!--
    SessionSyncTable — cross-component sync status for every Talk session.

    The status dot auto-refreshes every 30 seconds using a setInterval
    rather than a watch on a timestamp, because we want the refresh to
    happen regardless of whether anything in the store changed.
    The interval is cleared in onUnmounted so we don't leak it.
  -->
  <div class="sync-table">

    <!-- Track filter pills -->
    <div class="track-filters" role="group" aria-label="Filter by track">
      <button
        v-for="f in TRACK_FILTERS"
        :key="f.value"
        class="filter-pill"
        :class="{ 'pill--active': activeFilter === f.value }"
        @click="activeFilter = f.value"
      >
        {{ f.label }}
      </button>
    </div>

    <!-- Skeleton rows while loading -->
    <template v-if="isLoading">
      <div
        v-for="n in 3"
        :key="`skel-${n}`"
        class="skeleton-row"
        aria-hidden="true"
      />
    </template>

    <!-- Error state -->
    <div v-else-if="errorMessage" class="state-card state-card--error">
      <p>{{ errorMessage }}</p>
      <button class="btn-retry" @click="loadSessions">Retry</button>
    </div>

    <!-- Empty state -->
    <div v-else-if="filteredSessions.length === 0" class="state-card">
      <p>No sessions found{{ activeFilter !== 'all' ? ' in this track' : '' }}.</p>
    </div>

    <!-- Data table -->
    <table v-else class="table">
      <thead>
        <tr>
          <th class="col-status" aria-label="Status"></th>
          <th class="col-time">Time</th>
          <th class="col-title">Session</th>
          <th class="col-speaker">Speaker</th>
          <th class="col-track">Track</th>
          <th class="col-video" title="Video room linked">Video</th>
          <th class="col-gate" title="Ticket gate">Gate</th>
          <th class="col-mc" title="MC assigned">MC</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="session in filteredSessions" :key="session.id">
          <!-- Summary row -->
          <tr
            class="session-row"
            :class="{ 'row--expanded': expandedId === session.id }"
            tabindex="0"
            role="button"
            :aria-expanded="expandedId === session.id"
            @click="toggleExpand(session.id)"
            @keydown.enter.prevent="toggleExpand(session.id)"
            @keydown.space.prevent="toggleExpand(session.id)"
          >
            <td class="col-status">
              <span
                class="status-dot"
                :class="`dot--${session.status}`"
                :title="session.status"
              />
            </td>
            <td class="col-time">
              <small>{{ formatTime(session.start) }}</small>
            </td>
            <td class="col-title">{{ session.title }}</td>
            <td class="col-speaker">{{ session.speaker_name || '—' }}</td>
            <td class="col-track">
              <span v-if="session.track" class="track-badge">
                {{ session.track }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="col-video">
              <span
                class="sync-indicator"
                :class="session.video_room_id ? 'sync--ok' : 'sync--none'"
                :title="session.video_room_id ? session.video_room_id : 'No room'"
              >
                {{ session.video_room_id ? '✓' : '×' }}
              </span>
            </td>
            <td class="col-gate">
              <span
                v-if="settings.ticket_gate_enabled"
                class="badge badge--gate"
              >active</span>
              <span v-else class="text-muted">off</span>
            </td>
            <td class="col-mc">{{ session.mc_name || '—' }}</td>
          </tr>

          <!-- Expanded detail row -->
          <tr
            v-if="expandedId === session.id"
            class="detail-row"
            :key="`detail-${session.id}`"
          >
            <td colspan="8">
              <div class="detail-panel">
                <div class="detail-half">
                  <h4>Talk data</h4>
                  <dl>
                    <dt>Title</dt><dd>{{ session.title }}</dd>
                    <dt>State</dt><dd>{{ session.state }}</dd>
                    <dt>Speaker</dt><dd>{{ session.speaker_name || '—' }}</dd>
                    <dt>Abstract</dt>
                    <dd class="abstract">{{ session.abstract || '—' }}</dd>
                  </dl>
                </div>
                <div class="detail-half">
                  <h4>Sync status</h4>
                  <dl>
                    <dt>Video room</dt>
                    <dd>{{ session.video_room_id || 'Not synced' }}</dd>
                    <dt>Ticket gate</dt>
                    <dd>{{ settings.ticket_gate_enabled ? 'Active' : 'Inactive' }}</dd>
                    <dt>MC</dt>
                    <dd>{{ session.mc_name || 'Not assigned' }}</dd>
                    <dt>Last sync</dt>
                    <dd>{{ session.last_synced ? relativeTime(session.last_synced) : '—' }}</dd>
                  </dl>
                </div>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { usePluginSync } from '../composables/usePluginSync'

const props = defineProps({
  eventSlug: {
    type: String,
    required: true,
  },
  /** Pass down the current IntegrationSettings so the table can reflect
      the ticket gate state without making its own API call. */
  settings: {
    type: Object,
    required: true,
  },
})

const TRACK_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'main', label: 'Main' },
  { value: 'workshop', label: 'Workshop' },
  { value: 'lightning', label: 'Lightning' },
]

const activeFilter = ref('all')
const expandedId = ref(null)

const { sessions, isSyncing: isLoading, error, loadSessions } = usePluginSync(props.eventSlug)

// Surface error as a plain string so the template doesn't need to know
// whether error is a ref<string> or ref<Error>.
const errorMessage = computed(() => {
  if (!error.value) return null
  return typeof error.value === 'string' ? error.value : error.value.message
})

const filteredSessions = computed(() => {
  if (activeFilter.value === 'all') return sessions.value
  return sessions.value.filter(
    s => (s.track || '').toLowerCase() === activeFilter.value,
  )
})

function toggleExpand(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function formatTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function relativeTime(iso) {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  return `${Math.floor(diff / 3600)} hr ago`
}

// Refresh status dots every 30 s so "live" sessions update without a page reload.
let refreshTimer = null

onMounted(() => {
  refreshTimer = setInterval(loadSessions, 30_000)
})

onUnmounted(() => {
  clearInterval(refreshTimer)
})
</script>

<style scoped>
.sync-table {
  width: 100%;
}

/* ── Track filters ── */
.track-filters {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.filter-pill {
  padding: 3px 12px;
  border-radius: 12px;
  border: 1px solid var(--color-border, #ddd);
  background: #fff;
  font-size: 0.8rem;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.filter-pill:hover {
  background: var(--color-bg-hover, #f5f5f5);
}

.pill--active {
  background: var(--color-primary, #333);
  color: #fff;
  border-color: var(--color-primary, #333);
}

/* ── Skeleton rows ── */
.skeleton-row {
  height: 42px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
  margin-bottom: 4px;
  border-radius: 4px;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ── State cards ── */
.state-card {
  padding: 2rem;
  text-align: center;
  color: var(--color-text-muted, #888);
  border: 1px dashed var(--color-border, #ddd);
  border-radius: 6px;
}

.state-card--error {
  border-color: #e53935;
  color: #c62828;
}

.btn-retry {
  margin-top: 0.5rem;
  padding: 4px 16px;
  border: 1px solid currentColor;
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  font-size: 0.875rem;
}

/* ── Table ── */
.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.table th {
  font-weight: 600;
  padding: 6px 8px;
  border-bottom: 2px solid var(--color-border, #ddd);
  text-align: left;
  white-space: nowrap;
}

.table td {
  padding: 8px;
  border-bottom: 1px solid var(--color-border, #f0f0f0);
  vertical-align: middle;
}

.session-row {
  cursor: pointer;
  transition: background 0.1s;
}

.session-row:hover,
.session-row:focus {
  background: var(--color-bg-hover, #fafafa);
  outline: none;
}

.session-row.row--expanded {
  background: var(--color-bg-hover, #fafafa);
}

/* ── Status dot ── */
.status-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #bbb;
}

.dot--live { background: #e53935; }
.dot--upcoming { background: #43a047; }
.dot--ended { background: #bdbdbd; }

/* ── Track badge ── */
.track-badge {
  font-size: 0.7rem;
  padding: 1px 7px;
  border-radius: 10px;
  background: #e3f2fd;
  color: #1565c0;
}

/* ── Sync indicator ── */
.sync-indicator {
  font-weight: 700;
  font-size: 0.9rem;
}

.sync--ok { color: #2e7d32; }
.sync--none { color: #bdbdbd; }

/* ── Gate badge ── */
.badge--gate {
  font-size: 0.7rem;
  padding: 1px 7px;
  border-radius: 10px;
  background: #fff3e0;
  color: #e65100;
}

/* ── Expanded detail panel ── */
.detail-row td {
  padding: 0;
  background: var(--color-bg-hover, #fafafa);
}

.detail-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  padding: 1rem 1rem 1rem 2.5rem;
  border-left: 3px solid var(--color-primary, #333);
}

.detail-half h4 {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted, #888);
  margin: 0 0 0.5rem;
}

.detail-panel dl {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 4px 8px;
  margin: 0;
}

.detail-panel dt {
  font-weight: 600;
  font-size: 0.8rem;
}

.detail-panel dd {
  margin: 0;
  font-size: 0.8rem;
}

.abstract {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  color: var(--color-text-muted, #555);
}

.text-muted { color: var(--color-text-muted, #aaa); }

.col-status { width: 24px; }
.col-time { width: 60px; }
.col-track { width: 90px; }
.col-video,
.col-gate,
.col-mc { width: 80px; }
</style>
