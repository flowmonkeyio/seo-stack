<script setup lang="ts">
import StatusBadge from '../StatusBadge.vue'
import UiButton from '../ui/UiButton.vue'
import UiCard from '../ui/UiCard.vue'

defineProps<{
  name: string
  cron: string
  status: string
  nextRunAt?: string | null
  concurrencyLimit?: number | null
}>()

defineEmits<{
  (e: 'edit'): void
  (e: 'runNow'): void
  (e: 'disable'): void
}>()
</script>

<template>
  <UiCard density="compact">
    <template #header>
      <div class="min-w-0">
        <h3 class="truncate text-sm font-semibold text-fg-strong">
          {{ name }}
        </h3>
        <p class="font-mono text-xs text-fg-muted">
          {{ cron }}
        </p>
      </div>
      <StatusBadge
        kind="job"
        :status="status"
      />
    </template>
    <dl class="grid grid-cols-2 gap-3 text-xs">
      <div>
        <dt class="text-fg-muted">
          Next run
        </dt>
        <dd class="font-mono text-fg-strong">
          {{ nextRunAt ?? 'Not scheduled' }}
        </dd>
      </div>
      <div>
        <dt class="text-fg-muted">
          Concurrency
        </dt>
        <dd class="font-mono text-fg-strong">
          {{ concurrencyLimit ?? 'default' }}
        </dd>
      </div>
    </dl>
    <template #footer>
      <UiButton
        size="sm"
        variant="ghost"
        @click="$emit('disable')"
      >
        Disable
      </UiButton>
      <UiButton
        size="sm"
        variant="secondary"
        @click="$emit('edit')"
      >
        Edit
      </UiButton>
      <UiButton
        size="sm"
        variant="primary"
        @click="$emit('runNow')"
      >
        Run now
      </UiButton>
    </template>
  </UiCard>
</template>
