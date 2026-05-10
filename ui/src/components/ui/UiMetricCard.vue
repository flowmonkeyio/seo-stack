<!--
  UiMetricCard — single number with optional delta and sparkline slot.
  Use in dashboards. Don't decorate beyond label + value + delta.
-->
<script setup lang="ts">
import { computed } from 'vue';

export interface UiMetricCardProps {
  label: string;
  value: string | number;
  /** Optional unit shown smaller after value. */
  unit?: string;
  /** Numeric delta — positive/negative determines tone unless `deltaTone` set. */
  delta?: number | string;
  deltaLabel?: string;
  /** Forces tone of delta. */
  deltaTone?: 'positive' | 'negative' | 'neutral';
  /** When true, "negative" delta is good (e.g. cost dropping). */
  invertDelta?: boolean;
  /** Display compact density (h: 64px). */
  density?: 'compact' | 'comfortable';
  /** Loading state — shows skeleton. */
  loading?: boolean;
}

const props = withDefaults(defineProps<UiMetricCardProps>(), {
  unit: undefined,
  delta: undefined,
  deltaLabel: undefined,
  deltaTone: undefined,
  density: 'comfortable',
});

const deltaToneResolved = computed(() => {
  if (props.deltaTone) return props.deltaTone;
  if (typeof props.delta !== 'number') return 'neutral';
  if (props.delta === 0) return 'neutral';
  const positive = props.delta > 0;
  const isGood = props.invertDelta ? !positive : positive;
  return isGood ? 'positive' : 'negative';
});

const deltaToneClass = computed(() => ({
  positive: 'text-success-fg',
  negative: 'text-danger-fg',
  neutral:  'text-fg-muted',
}[deltaToneResolved.value]));

const deltaIcon = computed(() => ({
  positive: 'M12 19V5M5 12l7-7 7 7',
  negative: 'M12 5v14m-7-7 7 7 7-7',
  neutral:  'M5 12h14',
}[deltaToneResolved.value]));
</script>

<template>
  <div
    :class="[
      'ui-metric-card rounded-md border border-default bg-bg-surface',
      density === 'comfortable' ? 'p-4' : 'p-3',
    ]"
  >
    <p class="t-overline text-fg-subtle">
      {{ label }}
    </p>
    <div class="mt-1 flex items-baseline gap-2">
      <p
        v-if="loading"
        class="ui-skeleton block bg-bg-sunken animate-pulse rounded-xs"
        :style="{ width: '5ch', height: density === 'comfortable' ? '32px' : '24px' }"
      />
      <template v-else>
        <span :class="['font-semibold tabular-nums text-fg-strong', density === 'comfortable' ? 'text-2xl' : 'text-xl']">{{ value }}</span>
        <span
          v-if="unit"
          class="text-sm text-fg-muted"
        >{{ unit }}</span>
      </template>
    </div>
    <div
      v-if="(delta !== undefined && delta !== null) || $slots.spark"
      class="mt-2 flex items-center justify-between gap-2"
    >
      <span
        v-if="delta !== undefined && delta !== null"
        :class="['inline-flex items-center gap-1 text-xs font-medium', deltaToneClass]"
      >
        <svg
          width="11"
          height="11"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path :d="deltaIcon" />
        </svg>
        <span>{{ delta }}</span>
        <span
          v-if="deltaLabel"
          class="text-fg-subtle font-normal"
        >· {{ deltaLabel }}</span>
      </span>
      <div
        v-if="$slots.spark"
        class="flex-1 max-w-[60%]"
      >
        <slot name="spark" />
      </div>
    </div>
  </div>
</template>
