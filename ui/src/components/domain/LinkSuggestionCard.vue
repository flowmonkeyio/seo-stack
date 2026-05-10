<script setup lang="ts">
import StatusBadge from '../StatusBadge.vue'
import UiButton from '../ui/UiButton.vue'
import UiCard from '../ui/UiCard.vue'

defineProps<{
  fromTitle: string
  toTitle: string
  anchor: string
  score?: number | null
  status?: string
  reason?: string | null
}>()

defineEmits<{
  (e: 'apply'): void
  (e: 'dismiss'): void
  (e: 'open'): void
}>()
</script>

<template>
  <UiCard density="compact">
    <template #header>
      <div class="min-w-0">
        <h3 class="truncate text-sm font-semibold text-fg-strong">
          {{ anchor }}
        </h3>
        <p class="truncate text-xs text-fg-muted">
          {{ fromTitle }} -> {{ toTitle }}
        </p>
      </div>
      <StatusBadge
        kind="interlink"
        :status="status ?? 'suggested'"
      />
    </template>
    <p
      v-if="reason"
      class="text-sm text-fg-muted"
    >
      {{ reason }}
    </p>
    <p
      v-if="typeof score === 'number'"
      class="mt-3 font-mono text-xs text-fg-muted"
    >
      score {{ Math.round(score * 100) }}%
    </p>
    <template #footer>
      <UiButton
        size="sm"
        variant="ghost"
        @click="$emit('open')"
      >
        Inspect
      </UiButton>
      <UiButton
        size="sm"
        variant="secondary"
        @click="$emit('dismiss')"
      >
        Dismiss
      </UiButton>
      <UiButton
        size="sm"
        variant="primary"
        @click="$emit('apply')"
      >
        Apply
      </UiButton>
    </template>
  </UiCard>
</template>
