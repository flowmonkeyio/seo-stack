<script setup lang="ts">
import UiCard from '../ui/UiCard.vue'

const props = defineProps<{
  spent: number
  cap: number
  currency?: string
  period?: string
}>()

const pct = () => Math.min(100, (props.spent / props.cap) * 100)
const tone = () => (pct() >= 100 ? 'danger' : pct() >= 80 ? 'warning' : 'success')
const sym = () => props.currency || '$'
</script>

<template>
  <UiCard density="compact">
    <p class="text-2xs uppercase text-fg-subtle font-semibold">
      Spend{{ period ? ` · ${period}` : '' }}
    </p>
    <p class="text-2xl font-semibold tabular-nums mt-1">
      {{ sym() }}{{ spent.toFixed(0) }}<span class="text-sm text-fg-muted font-normal">/{{ sym() }}{{ cap.toFixed(0) }}</span>
    </p>
    <div class="h-1.5 rounded-full bg-bg-sunken mt-2 overflow-hidden">
      <div
        class="h-full rounded-full transition-all"
        :class="{
          'bg-success': tone() === 'success',
          'bg-warning': tone() === 'warning',
          'bg-danger': tone() === 'danger',
        }"
        :style="{ width: pct() + '%' }"
      />
    </div>
    <p class="text-xs text-fg-muted mt-1.5 tabular-nums">
      {{ pct().toFixed(0) }}% used
    </p>
  </UiCard>
</template>
