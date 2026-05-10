<script setup lang="ts">
import UiMetricCard from '../ui/UiMetricCard.vue'

defineProps<{
  metrics: {
    label: string
    value: string | number
    delta?: string | number
    deltaTone?: 'positive' | 'negative' | 'neutral'
  }[]
}>()
</script>

<template>
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
    <UiMetricCard
      v-for="m in metrics"
      :key="m.label"
      :label="m.label"
      :value="m.value"
      :delta="m.delta"
      :delta-tone="m.deltaTone"
    />
  </div>
</template>
