<script setup lang="ts">
const STEPS = ['brief', 'outline', 'draft', 'edited', 'review', 'approved', 'published'] as const
type Step = typeof STEPS[number]

const props = defineProps<{ current: Step; failed?: boolean }>()

function stateOf(s: Step): 'done' | 'current' | 'todo' {
  const ci = STEPS.indexOf(props.current)
  const si = STEPS.indexOf(s)
  if (si < ci) return 'done'
  if (si === ci) return 'current'
  return 'todo'
}
</script>

<template>
  <ol
    class="flex items-center gap-1 overflow-x-auto"
    aria-label="Article status"
  >
    <li
      v-for="(s, i) in STEPS"
      :key="s"
      class="flex items-center gap-1 shrink-0"
    >
      <div
        class="flex items-center gap-1.5 px-2 h-6 rounded text-2xs font-medium uppercase"
        :class="{
          'bg-success-subtle text-success-fg': stateOf(s) === 'done' && !failed,
          'bg-accent text-fg-on-accent': stateOf(s) === 'current' && !failed,
          'bg-danger-subtle text-danger-fg': stateOf(s) === 'current' && failed,
          'bg-bg-surface-alt text-fg-subtle border border-border-subtle': stateOf(s) === 'todo',
        }"
      >
        <span class="font-mono opacity-70">{{ i + 1 }}</span>
        <span>{{ s }}</span>
      </div>
      <div
        v-if="i < STEPS.length - 1"
        class="w-3 h-px bg-border-default"
      />
    </li>
  </ol>
</template>
