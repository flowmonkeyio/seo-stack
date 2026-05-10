<script setup lang="ts">
import UiCard from '../ui/UiCard.vue'
import UiButton from '../ui/UiButton.vue'
import UiBadge from '../ui/UiBadge.vue'

defineProps<{
  provider: string
  description?: string
  iconUrl?: string
  health?: 'healthy' | 'degraded' | 'down' | 'unconfigured'
  connected?: boolean
}>()

defineEmits<{ (e: 'connect'): void; (e: 'configure'): void; (e: 'disconnect'): void }>()

const healthTone = {
  healthy: 'success',
  degraded: 'warning',
  down: 'danger',
  unconfigured: 'neutral',
} as const
</script>

<template>
  <UiCard padding="md" class="flex items-start gap-3">
    <div v-if="iconUrl" class="w-9 h-9 rounded bg-bg-surface-alt flex items-center justify-center shrink-0">
      <img :src="iconUrl" :alt="provider" class="w-6 h-6" />
    </div>
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <h3 class="text-sm font-semibold text-fg-strong truncate">{{ provider }}</h3>
        <UiBadge v-if="health" :tone="healthTone[health]" size="sm">{{ health }}</UiBadge>
      </div>
      <p v-if="description" class="text-xs text-fg-muted mt-0.5">{{ description }}</p>
    </div>
    <div class="flex gap-2 shrink-0">
      <UiButton v-if="!connected" variant="primary" size="sm" @click="$emit('connect')">Connect</UiButton>
      <template v-else>
        <UiButton variant="secondary" size="sm" @click="$emit('configure')">Configure</UiButton>
        <UiButton variant="ghost" size="sm" @click="$emit('disconnect')">Disconnect</UiButton>
      </template>
    </div>
  </UiCard>
</template>
