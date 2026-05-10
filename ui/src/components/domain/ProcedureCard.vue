<script setup lang="ts">
import StatusBadge from '../StatusBadge.vue'
import UiButton from '../ui/UiButton.vue'
import UiCard from '../ui/UiCard.vue'

defineProps<{
  name: string
  slug: string
  description?: string | null
  status?: string
  lastRunAt?: string | null
  disabled?: boolean
}>()

defineEmits<{
  (e: 'run'): void
  (e: 'viewRuns'): void
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
          {{ slug }}
        </p>
      </div>
      <StatusBadge
        domain="procedure"
        :status="status ?? 'enabled'"
      />
    </template>

    <p class="text-sm text-fg-muted">
      {{ description ?? 'Procedure ready to run.' }}
    </p>
    <p class="mt-3 text-xs text-fg-muted">
      Last run:
      <span class="font-mono text-fg-default">{{ lastRunAt ?? 'Never' }}</span>
    </p>

    <template #footer>
      <UiButton
        size="sm"
        variant="ghost"
        @click="$emit('viewRuns')"
      >
        Runs
      </UiButton>
      <UiButton
        size="sm"
        variant="primary"
        :disabled="disabled"
        @click="$emit('run')"
      >
        Run procedure
      </UiButton>
    </template>
  </UiCard>
</template>
