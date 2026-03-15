<template>
  <!--
    IntegrationCard — one card per integration feature.

    The toggle never touches the prop directly; it emits so the parent
    can decide whether to optimistically update or wait for an API response.
    The config slot is only rendered when enabled is true, and the
    expand/collapse height transition is pure CSS so we avoid pulling in
    an animation library for something this small.
  -->
  <div
    class="integration-card"
    :class="{ 'is-loading': isLoading, 'is-enabled': enabled }"
    :aria-busy="isLoading"
  >
    <div class="card-header">
      <span class="card-icon" role="img" :aria-label="title">{{ icon }}</span>

      <div class="card-meta">
        <h3 class="card-title">{{ title }}</h3>
        <p class="card-desc">{{ description }}</p>
      </div>

      <div class="card-controls">
        <!-- Status badge -->
        <span
          class="status-badge"
          :class="enabled ? 'badge--active' : 'badge--off'"
        >
          {{ enabled ? 'Active' : 'Disabled' }}
        </span>

        <!-- The actual toggle.  Disabled while a save/sync is in flight so
             an organiser can't queue multiple conflicting requests. -->
        <button
          class="toggle-switch"
          role="switch"
          :aria-checked="enabled"
          :aria-label="`Toggle ${title}`"
          :disabled="isLoading"
          @click="handleToggle"
        >
          <span class="toggle-thumb" />
        </button>
      </div>
    </div>

    <!-- Last-synced timestamp — only shown when a time is available -->
    <p v-if="lastSynced" class="card-synced">
      Last synced {{ relativeTime(lastSynced) }}
    </p>

    <!--
      Config slot: expand/collapse via max-height transition.
      max-height animates from 0 to a large-enough value; the exact
      content height doesn't need to be known in advance.
    -->
    <div
      class="card-config"
      :class="{ 'config--open': enabled }"
      :aria-hidden="!enabled"
    >
      <slot name="config" />
    </div>

    <!-- Loading overlay — sits on top of the card content -->
    <div v-if="isLoading" class="card-overlay" aria-hidden="true">
      <span class="spinner" />
    </div>
  </div>
</template>

<script setup>
/**
 * IntegrationCard — reusable toggle card for one integration feature.
 *
 * Props flow down, events flow up.  The parent (PluginAdminPanel) owns
 * the enabled state; this component just asks to change it.
 */

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  icon: {
    type: String,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    required: true,
  },
  enabled: {
    type: Boolean,
    required: true,
  },
  /** ISO 8601 timestamp string, e.g. from lastSyncAt in the store. */
  lastSynced: {
    type: String,
    default: null,
  },
  /** True while the parent is saving or syncing — disables the toggle. */
  isLoading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits({
  /** Emitted when the toggle is clicked.  Payload: the new boolean value. */
  toggle: (value) => typeof value === 'boolean',
})

function handleToggle() {
  if (!props.isLoading) {
    emit('toggle', !props.enabled)
  }
}

/**
 * Convert an ISO timestamp to a human-readable relative string.
 * We deliberately keep this simple rather than pulling in date-fns for
 * something only shown on admin pages.
 */
function relativeTime(iso) {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} hr ago`
  return `${Math.floor(diff / 86400)} days ago`
}
</script>

<style scoped>
.integration-card {
  position: relative;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 0.75rem;
  background: var(--color-card-bg, #fff);
  transition: border-color 0.15s ease;
}

.integration-card.is-enabled {
  border-left: 3px solid var(--color-success, #2e7d32);
}

.card-header {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.card-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
  line-height: 1;
}

.card-meta {
  flex: 1;
}

.card-title {
  margin: 0 0 0.25rem;
  font-size: 1rem;
  font-weight: 600;
}

.card-desc {
  margin: 0;
  font-size: 0.875rem;
  color: var(--color-text-muted, #666);
  line-height: 1.4;
}

.card-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

/* ── Status badge ── */
.status-badge {
  font-size: 0.75rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}

.badge--active {
  background: #e8f5e9;
  color: #2e7d32;
}

.badge--off {
  background: #f5f5f5;
  color: #757575;
}

/* ── Toggle switch — CSS only, no JS animation library ── */
.toggle-switch {
  appearance: none;
  width: 40px;
  height: 22px;
  border-radius: 11px;
  background: var(--color-border, #ccc);
  border: none;
  cursor: pointer;
  position: relative;
  transition: background 0.2s ease;
  flex-shrink: 0;
}

.toggle-switch[aria-checked='true'] {
  background: var(--color-success, #2e7d32);
}

.toggle-switch:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toggle-thumb {
  display: block;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  position: absolute;
  top: 3px;
  left: 3px;
  transition: transform 0.2s ease;
  pointer-events: none;
}

.toggle-switch[aria-checked='true'] .toggle-thumb {
  transform: translateX(18px);
}

/* ── Config slot expand/collapse ── */
.card-config {
  overflow: hidden;
  max-height: 0;
  /* 500px cap is more than enough for any config section we'd ever add */
  transition: max-height 0.25s ease, opacity 0.2s ease, padding-top 0.25s ease;
  opacity: 0;
  padding-top: 0;
}

.card-config.config--open {
  max-height: 500px;
  opacity: 1;
  padding-top: 0.75rem;
}

/* ── Last synced line ── */
.card-synced {
  font-size: 0.75rem;
  color: var(--color-text-muted, #999);
  margin: 0.35rem 0 0;
}

/* ── Loading overlay ── */
.card-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.65);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.spinner {
  display: block;
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-border, #ccc);
  border-top-color: var(--color-primary, #333);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
