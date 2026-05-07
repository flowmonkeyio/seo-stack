<script setup lang="ts">
// StatusBadge — single-purpose pill rendering a colored status label.
//
// `kind` selects the table of allowed statuses (per PLAN.md status enums
// in §"Status enums"). Unknown statuses fall through to a neutral grey
// so we never silently render an empty/transparent badge.
//
// Color mapping is high-contrast Tailwind 100/800 (light) +
// 900/40 + 300 (dark) which clears axe AA contrast on every shade.

import { computed } from 'vue'

type Kind = 'topic' | 'article' | 'run' | 'interlink' | 'project' | 'publish' | 'job'

interface Props {
  status: string
  kind: Kind
  /** When true, renders a smaller variant suitable for inline rows. */
  small?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  small: false,
})

// Each table value is a tailwind class name pair: bg + text.
type Pair = [string, string]

const TOPIC: Record<string, Pair> = {
  queued: ['bg-gray-100 dark:bg-gray-800', 'text-gray-700 dark:text-gray-300'],
  approved: ['bg-blue-100 dark:bg-blue-900/40', 'text-blue-800 dark:text-blue-300'],
  drafting: ['bg-amber-100 dark:bg-amber-900/40', 'text-amber-800 dark:text-amber-300'],
  published: ['bg-emerald-100 dark:bg-emerald-900/40', 'text-emerald-800 dark:text-emerald-300'],
  rejected: ['bg-red-100 dark:bg-red-900/40', 'text-red-800 dark:text-red-300'],
}

const ARTICLE: Record<string, Pair> = {
  briefing: ['bg-blue-100 dark:bg-blue-900/40', 'text-blue-800 dark:text-blue-300'],
  outlined: ['bg-blue-100 dark:bg-blue-900/40', 'text-blue-800 dark:text-blue-300'],
  drafted: ['bg-amber-100 dark:bg-amber-900/40', 'text-amber-800 dark:text-amber-300'],
  edited: ['bg-amber-100 dark:bg-amber-900/40', 'text-amber-800 dark:text-amber-300'],
  eeat_passed: ['bg-purple-100 dark:bg-purple-900/40', 'text-purple-800 dark:text-purple-300'],
  published: ['bg-emerald-100 dark:bg-emerald-900/40', 'text-emerald-800 dark:text-emerald-300'],
  refresh_due: ['bg-orange-100 dark:bg-orange-900/40', 'text-orange-800 dark:text-orange-300'],
  'aborted-publish': ['bg-red-100 dark:bg-red-900/40', 'text-red-800 dark:text-red-300'],
}

const RUN: Record<string, Pair> = {
  running: ['bg-blue-100 dark:bg-blue-900/40', 'text-blue-800 dark:text-blue-300'],
  success: ['bg-emerald-100 dark:bg-emerald-900/40', 'text-emerald-800 dark:text-emerald-300'],
  failed: ['bg-red-100 dark:bg-red-900/40', 'text-red-800 dark:text-red-300'],
  aborted: ['bg-gray-200 dark:bg-gray-700', 'text-gray-700 dark:text-gray-200'],
}

const INTERLINK: Record<string, Pair> = {
  suggested: ['bg-amber-100 dark:bg-amber-900/40', 'text-amber-800 dark:text-amber-300'],
  applied: ['bg-emerald-100 dark:bg-emerald-900/40', 'text-emerald-800 dark:text-emerald-300'],
  dismissed: ['bg-gray-100 dark:bg-gray-800', 'text-gray-700 dark:text-gray-300'],
  broken: ['bg-red-100 dark:bg-red-900/40', 'text-red-800 dark:text-red-300'],
}

const PROJECT: Record<string, Pair> = {
  active: ['bg-emerald-100 dark:bg-emerald-900/40', 'text-emerald-800 dark:text-emerald-300'],
  inactive: ['bg-gray-100 dark:bg-gray-800', 'text-gray-700 dark:text-gray-300'],
}

const PUBLISH: Record<string, Pair> = {
  pending: ['bg-amber-100 dark:bg-amber-900/40', 'text-amber-800 dark:text-amber-300'],
  published: ['bg-emerald-100 dark:bg-emerald-900/40', 'text-emerald-800 dark:text-emerald-300'],
  failed: ['bg-red-100 dark:bg-red-900/40', 'text-red-800 dark:text-red-300'],
  reverted: ['bg-gray-200 dark:bg-gray-700', 'text-gray-700 dark:text-gray-200'],
}

const JOB: Record<string, Pair> = {
  pending: ['bg-amber-100 dark:bg-amber-900/40', 'text-amber-800 dark:text-amber-300'],
  running: ['bg-blue-100 dark:bg-blue-900/40', 'text-blue-800 dark:text-blue-300'],
  success: ['bg-emerald-100 dark:bg-emerald-900/40', 'text-emerald-800 dark:text-emerald-300'],
  failed: ['bg-red-100 dark:bg-red-900/40', 'text-red-800 dark:text-red-300'],
  skipped: ['bg-gray-100 dark:bg-gray-800', 'text-gray-700 dark:text-gray-300'],
}

const TABLES: Record<Kind, Record<string, Pair>> = {
  topic: TOPIC,
  article: ARTICLE,
  run: RUN,
  interlink: INTERLINK,
  project: PROJECT,
  publish: PUBLISH,
  job: JOB,
}

const NEUTRAL: Pair = ['bg-gray-100 dark:bg-gray-800', 'text-gray-700 dark:text-gray-300']

const classes = computed<string>(() => {
  const table = TABLES[props.kind] ?? {}
  const [bg, fg] = table[props.status] ?? NEUTRAL
  const size = props.small
    ? 'px-1.5 py-0.5 text-[10px]'
    : 'px-2.5 py-0.5 text-xs'
  return `inline-flex items-center gap-1 rounded-full font-medium ${size} ${bg} ${fg}`
})
</script>

<template>
  <span
    :class="classes"
    :data-status="status"
    :data-kind="kind"
  >
    <slot>{{ status }}</slot>
  </span>
</template>
