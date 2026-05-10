<script setup lang="ts">
import StatusBadge from '../StatusBadge.vue'
import UiButton from '../ui/UiButton.vue'
import UiCard from '../ui/UiCard.vue'

defineProps<{
  title: string
  severity: string
  score?: number | null
  checkedAt?: string | null
  changedFields?: string[]
}>()

defineEmits<{
  (e: 'openDiff'): void
  (e: 'acceptBaseline'): void
}>()
</script>

<template>
  <UiCard density="compact">
    <template #header>
      <div class="min-w-0">
        <h3 class="truncate text-sm font-semibold text-fg-strong">
          {{ title }}
        </h3>
        <p class="font-mono text-xs text-fg-muted">
          {{ checkedAt ?? 'Not checked' }}
        </p>
      </div>
      <StatusBadge
        domain="drift"
        :status="severity"
      />
    </template>
    <div class="flex items-center justify-between gap-3">
      <p class="text-sm text-fg-muted">
        Score
        <span class="font-mono text-fg-strong">{{ score == null ? 'n/a' : score.toFixed(2) }}</span>
      </p>
      <p class="truncate text-xs text-fg-muted">
        {{ changedFields?.length ? changedFields.join(', ') : 'No changed fields recorded' }}
      </p>
    </div>
    <template #footer>
      <UiButton
        size="sm"
        variant="ghost"
        @click="$emit('acceptBaseline')"
      >
        Accept baseline
      </UiButton>
      <UiButton
        size="sm"
        variant="primary"
        @click="$emit('openDiff')"
      >
        View diff
      </UiButton>
    </template>
  </UiCard>
</template>
