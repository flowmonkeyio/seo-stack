<script setup lang="ts">
import UiCard from '../ui/UiCard.vue'
import UiBadge from '../ui/UiBadge.vue'

const props = defineProps<{
  score: number          // 0-100
  verdict: 'unevaluated' | 'failing' | 'marginal' | 'passing' | 'exemplary'
  breakdown?: { label: string; value: number }[]
}>()

const verdictTone = {
  unevaluated: 'neutral',
  failing: 'danger',
  marginal: 'warning',
  passing: 'eeat',
  exemplary: 'eeat',
} as const

const dasharray = 125.6
const offset = (s: number) => dasharray * (1 - Math.max(0, Math.min(100, s)) / 100)
</script>

<template>
  <UiCard density="compact">
    <div class="flex items-center gap-4">
      <svg
        width="64"
        height="64"
        viewBox="0 0 48 48"
        class="shrink-0"
      >
        <circle
          cx="24"
          cy="24"
          r="20"
          fill="none"
          stroke="var(--color-bg-sunken)"
          stroke-width="5"
        />
        <circle
          cx="24"
          cy="24"
          r="20"
          fill="none"
          stroke="var(--color-eeat-default)"
          stroke-width="5"
          stroke-linecap="round"
          :stroke-dasharray="dasharray"
          :stroke-dashoffset="offset(props.score)"
          transform="rotate(-90 24 24)"
        />
      </svg>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
          <p class="text-2xl font-semibold tabular-nums text-fg-strong">
            {{ score }}
          </p>
          <UiBadge :tone="verdictTone[verdict]">
            {{ verdict }}
          </UiBadge>
        </div>
        <p class="text-2xs uppercase text-fg-subtle font-semibold mt-0.5">
          EEAT
        </p>
      </div>
    </div>
    <ul
      v-if="breakdown?.length"
      class="mt-3 space-y-1.5"
    >
      <li
        v-for="b in breakdown"
        :key="b.label"
        class="flex items-center gap-2"
      >
        <span class="text-xs text-fg-muted w-24 shrink-0 truncate">{{ b.label }}</span>
        <div class="flex-1 h-1.5 rounded-full bg-bg-sunken overflow-hidden">
          <div
            class="h-full bg-eeat"
            :style="{ width: b.value + '%' }"
          />
        </div>
        <span class="font-mono text-xs tabular-nums text-fg-muted w-8 text-right">{{ b.value }}</span>
      </li>
    </ul>
  </UiCard>
</template>
