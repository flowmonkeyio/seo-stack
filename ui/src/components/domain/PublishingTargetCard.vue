<script setup lang="ts">
import StatusBadge from '../StatusBadge.vue'
import UiButton from '../ui/UiButton.vue'
import UiCard from '../ui/UiCard.vue'

defineProps<{
  name: string
  kind: string
  status: string
  url?: string | null
  lastPublishedAt?: string | null
  primary?: boolean
  disabled?: boolean
}>()

defineEmits<{
  (e: 'publish'): void
  (e: 'configure'): void
  (e: 'retry'): void
}>()
</script>

<template>
  <UiCard density="compact">
    <template #header>
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <h3 class="truncate text-sm font-semibold text-fg-strong">
            {{ name }}
          </h3>
          <StatusBadge
            v-if="primary"
            domain="project"
            status="active"
            label="Primary"
            no-icon
          />
        </div>
        <p class="mt-0.5 truncate text-xs text-fg-muted">
          {{ kind }}<template v-if="url">
            · {{ url }}
          </template>
        </p>
      </div>
      <StatusBadge
        domain="publish"
        :status="status"
      />
    </template>

    <p class="text-xs text-fg-muted">
      Last publish:
      <span class="font-mono text-fg-default">{{ lastPublishedAt ?? 'Never' }}</span>
    </p>

    <template #footer>
      <UiButton
        size="sm"
        variant="ghost"
        :disabled="disabled"
        @click="$emit('configure')"
      >
        Configure
      </UiButton>
      <UiButton
        v-if="status === 'failed'"
        size="sm"
        variant="secondary"
        :disabled="disabled"
        @click="$emit('retry')"
      >
        Retry
      </UiButton>
      <UiButton
        size="sm"
        variant="primary"
        :disabled="disabled"
        @click="$emit('publish')"
      >
        Publish
      </UiButton>
    </template>
  </UiCard>
</template>
