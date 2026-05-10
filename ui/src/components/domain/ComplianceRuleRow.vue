<script setup lang="ts">
import StatusBadge from '../StatusBadge.vue'
import UiButton from '../ui/UiButton.vue'

defineProps<{
  name: string
  kind: string
  position?: string | null
  required?: boolean
  active?: boolean
  lastCheckedAt?: string | null
}>()

defineEmits<{
  (e: 'edit'): void
  (e: 'toggle'): void
}>()
</script>

<template>
  <div class="flex items-center justify-between gap-4 rounded-md border border-default bg-bg-surface px-3 py-2">
    <div class="min-w-0">
      <div class="flex items-center gap-2">
        <h3 class="truncate text-sm font-medium text-fg-strong">
          {{ name }}
        </h3>
        <StatusBadge
          domain="project"
          :status="active === false ? 'paused' : 'active'"
          :label="active === false ? 'Inactive' : 'Active'"
          no-icon
        />
      </div>
      <p class="mt-0.5 truncate text-xs text-fg-muted">
        {{ kind }}<template v-if="position">
          · {{ position }}
        </template>
        <template v-if="required">
          · required
        </template>
        <template v-if="lastCheckedAt">
          · checked {{ lastCheckedAt }}
        </template>
      </p>
    </div>
    <div class="flex shrink-0 items-center gap-2">
      <UiButton
        size="sm"
        variant="ghost"
        @click="$emit('toggle')"
      >
        {{ active === false ? 'Enable' : 'Disable' }}
      </UiButton>
      <UiButton
        size="sm"
        variant="secondary"
        @click="$emit('edit')"
      >
        Edit
      </UiButton>
    </div>
  </div>
</template>
