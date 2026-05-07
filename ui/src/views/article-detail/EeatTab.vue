<script setup lang="ts">
// EeatTab (article-detail) — score summary + evaluations table + veto banner.
//
// PLAN.md L1012-L1031:
//   BLOCK = any tier='core' (T04/C01/R10) verdict='fail' → cannot ship.
//   FIX   = any required=true verdict='fail' OR any of 8 dimensions < 70.
//   SHIP  = all cores pass, no required fail, all 8 dimensions ≥ 70.
//
// We display:
//   - Top: vetoes_failed banner (red) if any
//   - Dimension grid: 8 dimensions with score gauge
//   - System scores: GEO + SEO
//   - Evaluations DataTable: criterion / verdict / notes
//
// Failed items highlighted red, partial amber, pass green. Veto items
// (T04/C01/R10) get a "core" badge.

import { computed, onMounted, ref, watch } from 'vue'

import DataTable from '@/components/DataTable.vue'
import { apiFetch } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type EeatReport = components['schemas']['EeatReportResponse']
type Evaluation = components['schemas']['EeatEvaluationOut']
type Criterion = components['schemas']['EeatCriterionOut']

const props = defineProps<{
  articleId: number
  projectId: number
}>()

const toasts = useToastsStore()

const report = ref<EeatReport | null>(null)
const criteriaIndex = ref<Record<number, Criterion>>({})
const loading = ref(false)

const columns: DataTableColumn<Evaluation>[] = [
  { key: 'criterion_id', label: 'Criterion' },
  { key: 'verdict', label: 'Verdict' },
  { key: 'notes', label: 'Notes' },
]

async function load(): Promise<void> {
  loading.value = true
  try {
    const [r, criteria] = await Promise.all([
      apiFetch<EeatReport>(`/api/v1/articles/${props.articleId}/eeat`),
      apiFetch<Criterion[]>(`/api/v1/projects/${props.projectId}/eeat`),
    ])
    report.value = r
    const idx: Record<number, Criterion> = {}
    for (const c of criteria) idx[c.id] = c
    criteriaIndex.value = idx
  } catch (err) {
    toasts.error('Failed to load EEAT report', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

const dimensions = computed<string[]>(() => Object.keys(report.value?.score.dimension_scores ?? {}))

const systemScores = computed<Array<[string, number]>>(() => {
  const m = report.value?.score.system_scores ?? {}
  return Object.entries(m)
})

const vetoesFailed = computed<string[]>(() => report.value?.score.vetoes_failed ?? [])

const verdictAggregate = computed<'SHIP' | 'FIX' | 'BLOCK' | 'unscored'>(() => {
  const r = report.value
  if (!r || r.evaluations.length === 0) return 'unscored'
  if (r.score.vetoes_failed.length > 0) return 'BLOCK'
  // FIX = any required=true criterion is fail OR any dimension < 70.
  const dims = Object.values(r.score.dimension_scores)
  if (dims.some((d) => d < 70)) return 'FIX'
  for (const ev of r.evaluations) {
    const c = criteriaIndex.value[ev.criterion_id]
    if (c?.required && ev.verdict === 'fail') return 'FIX'
  }
  return 'SHIP'
})

const verdictBadge = computed<{ label: string; classes: string }>(() => {
  switch (verdictAggregate.value) {
    case 'SHIP':
      return {
        label: 'SHIP',
        classes:
          'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
      }
    case 'FIX':
      return {
        label: 'FIX',
        classes: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
      }
    case 'BLOCK':
      return {
        label: 'BLOCK',
        classes: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
      }
    default:
      return {
        label: 'unscored',
        classes: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
      }
  }
})

function verdictPill(verdict: string): string {
  if (verdict === 'pass')
    return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200'
  if (verdict === 'partial')
    return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200'
  return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200'
}

function rowBg(ev: Evaluation): string {
  if (ev.verdict === 'fail') return 'bg-red-50 dark:bg-red-900/20'
  if (ev.verdict === 'partial') return 'bg-amber-50 dark:bg-amber-900/20'
  return ''
}

function criterionLabel(id: number): string {
  return criteriaIndex.value[id]?.code ?? `#${id}`
}

function isCore(id: number): boolean {
  return criteriaIndex.value[id]?.tier === 'core'
}

onMounted(load)
watch(() => props.articleId, load)
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-eeat-tab-title"
  >
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2
        id="cs-eeat-tab-title"
        class="text-base font-semibold"
      >
        EEAT report
      </h2>
      <span
        :class="['rounded px-2.5 py-1 text-sm font-semibold', verdictBadge.classes]"
        data-testid="cs-eeat-verdict"
      >
        verdict: {{ verdictBadge.label }}
      </span>
    </div>

    <div
      v-if="vetoesFailed.length > 0"
      class="rounded border border-red-300 bg-red-50 p-3 dark:border-red-700 dark:bg-red-900/40"
      role="alert"
      data-testid="cs-eeat-veto-banner"
    >
      <strong class="text-red-800 dark:text-red-200">Cannot ship — veto item failed.</strong>
      <p class="mt-1 text-sm text-red-700 dark:text-red-200">
        Failed core criteria:
        <span class="font-mono">{{ vetoesFailed.join(', ') }}</span>
      </p>
    </div>

    <div
      v-if="report && dimensions.length > 0"
      class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
    >
      <div
        v-for="dim in dimensions"
        :key="dim"
        class="rounded border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900"
      >
        <div class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
          {{ dim }}
        </div>
        <div class="mt-1 text-2xl font-semibold">
          {{ Math.round(report.score.dimension_scores[dim]) }}
        </div>
        <div class="mt-2 h-2 w-full overflow-hidden rounded bg-gray-200 dark:bg-gray-700">
          <div
            class="h-full"
            :class="
              report.score.dimension_scores[dim] >= 70
                ? 'bg-emerald-500'
                : report.score.dimension_scores[dim] >= 50
                  ? 'bg-amber-500'
                  : 'bg-red-500'
            "
            :style="{ width: `${Math.min(100, Math.max(0, report.score.dimension_scores[dim]))}%` }"
          />
        </div>
      </div>
    </div>

    <div
      v-if="systemScores.length > 0"
      class="grid gap-3 sm:grid-cols-2"
    >
      <div
        v-for="[name, score] in systemScores"
        :key="name"
        class="rounded border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900"
      >
        <div class="flex items-baseline justify-between">
          <span class="text-sm font-medium text-gray-600 dark:text-gray-400">{{ name }}</span>
          <span class="text-2xl font-semibold">{{ Math.round(score) }}</span>
        </div>
      </div>
    </div>

    <DataTable
      v-if="report"
      :items="report.evaluations"
      :columns="columns"
      :loading="loading"
      aria-label="EEAT evaluations"
      empty-message="No evaluations yet — run the EEAT gate to populate."
    >
      <template #cell:criterion_id="{ row }">
        <span class="inline-flex items-center gap-1">
          <span class="font-mono text-xs">{{ criterionLabel((row as Evaluation).criterion_id) }}</span>
          <span
            v-if="isCore((row as Evaluation).criterion_id)"
            class="rounded bg-red-100 px-1 py-0.5 text-[10px] font-medium text-red-800 dark:bg-red-900/40 dark:text-red-300"
            data-testid="cs-eeat-core-badge"
          >
            core
          </span>
        </span>
      </template>
      <template #cell:verdict="{ row }">
        <span :class="['rounded-full px-2 py-0.5 text-xs font-medium', verdictPill((row as Evaluation).verdict), rowBg(row as Evaluation)]">
          {{ (row as Evaluation).verdict }}
        </span>
      </template>
    </DataTable>

    <p
      v-if="!loading && report && report.evaluations.length === 0"
      class="rounded border border-dashed border-gray-300 p-4 text-sm text-gray-600 dark:border-gray-700 dark:text-gray-300"
    >
      No EEAT evaluations recorded yet for this article. The EEAT gate will
      populate them on the next procedure-4 run.
    </p>
  </section>
</template>
