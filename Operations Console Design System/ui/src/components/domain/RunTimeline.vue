<script setup lang="ts">
import UiBadge from '../ui/UiBadge.vue'
import UiProgressBar from '../ui/UiProgressBar.vue'

export interface RunStep {
  id: string
  label: string
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'skipped'
  detail?: string
  durationMs?: number
  progress?: number
}

defineProps<{ steps: RunStep[] }>()

function fmt(ms?: number) {
  if (!ms) return ''
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}
</script>

<template>
  <ol class="divide-y divide-border-subtle">
    <li
      v-for="(s, i) in steps"
      :key="s.id"
      class="px-4 py-3 flex items-start gap-3"
      :class="{ 'bg-info-subtle': s.status === 'running', 'opacity-60': s.status === 'pending' || s.status === 'skipped' }"
    >
      <div
        class="w-6 h-6 rounded-full flex items-center justify-center shrink-0 text-2xs"
        :class="{
          'bg-success-subtle text-success-fg': s.status === 'succeeded',
          'bg-info text-fg-on-accent': s.status === 'running',
          'bg-danger-subtle text-danger-fg': s.status === 'failed',
          'border border-dashed border-border-strong text-fg-subtle': s.status === 'pending' || s.status === 'skipped',
        }"
      >
        <svg v-if="s.status === 'succeeded'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="m5 12 5 5 9-12"/></svg>
        <svg v-else-if="s.status === 'failed'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M18 6 6 18M6 6l12 12"/></svg>
        <svg v-else-if="s.status === 'running'" class="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-opacity=".3" stroke-width="3"/><path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>
        <span v-else>{{ i + 1 }}</span>
      </div>
      <div class="flex-1 min-w-0">
        <div class="text-sm font-medium text-fg-strong">{{ s.label }}</div>
        <div v-if="s.detail" class="text-xs text-fg-muted mt-0.5">{{ s.detail }}</div>
        <UiProgressBar v-if="s.status === 'running' && s.progress !== undefined" :value="s.progress" tone="info" class="mt-2" />
      </div>
      <div class="text-xs text-fg-muted font-mono tabular-nums shrink-0">
        {{ s.status === 'running' ? 'running' : fmt(s.durationMs) }}
      </div>
    </li>
  </ol>
</template>
