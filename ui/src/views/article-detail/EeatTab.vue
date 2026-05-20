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

import { UiBadge } from '@/components/ui'
import { apiFetch, formatApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'

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

type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger'

interface CategoryMeta {
  title: string
  description: string
}

interface EvaluationRow {
  evaluation: Evaluation
  criterion: Criterion | null
  code: string
  category: string
  isCore: boolean
  required: boolean
}

interface EvaluationGroup {
  category: string
  title: string
  description: string
  rows: EvaluationRow[]
  pass: number
  partial: number
  fail: number
  core: number
  required: number
}

const CATEGORY_ORDER = ['C', 'O', 'R', 'E', 'Exp', 'Ept', 'A', 'T']

const CATEGORY_META: Record<string, CategoryMeta> = {
  C: {
    title: 'Content',
    description: 'Editorial completeness, scope, structure, and source fit.',
  },
  O: {
    title: 'Optimization',
    description: 'Search formatting, schema fit, and on-page presentation.',
  },
  R: {
    title: 'Reliability',
    description: 'Accuracy, citations, local evidence, and repeatability.',
  },
  E: {
    title: 'Experience',
    description: 'Original perspective and first-hand process evidence.',
  },
  Exp: {
    title: 'Expertise',
    description: 'Method, terminology, and operator competence.',
  },
  Ept: {
    title: 'Expertise',
    description: 'Method, terminology, and operator competence.',
  },
  A: {
    title: 'Authority',
    description: 'Authority signals, references, and credible boundaries.',
  },
  T: {
    title: 'Trust',
    description: 'Transparency, disclosure, policy, and safety checks.',
  },
}

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
    toasts.error('Failed to load EEAT report', formatApiError(err))
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

const evaluationRows = computed<EvaluationRow[]>(() =>
  (report.value?.evaluations ?? []).map((evaluation) => {
    const criterion = criteriaIndex.value[evaluation.criterion_id] ?? null
    const code = criterion?.code ?? `#${evaluation.criterion_id}`
    return {
      evaluation,
      criterion,
      code,
      category: criterion?.category ?? code.replace(/\d.*$/, ''),
      isCore: criterion?.tier === 'core',
      required: criterion?.required === true,
    }
  }),
)

const evaluationGroups = computed<EvaluationGroup[]>(() => {
  const byCategory = new Map<string, EvaluationRow[]>()
  for (const row of evaluationRows.value) {
    const rows = byCategory.get(row.category) ?? []
    rows.push(row)
    byCategory.set(row.category, rows)
  }

  return [...byCategory.entries()]
    .map(([category, rows]) => {
      const meta = CATEGORY_META[category] ?? {
        title: category,
        description: 'Article-level rubric checks.',
      }
      const sortedRows = [...rows].sort((a, b) => a.code.localeCompare(b.code, undefined, { numeric: true }))
      return {
        category,
        title: meta.title,
        description: meta.description,
        rows: sortedRows,
        pass: rows.filter((row) => row.evaluation.verdict === 'pass').length,
        partial: rows.filter((row) => row.evaluation.verdict === 'partial').length,
        fail: rows.filter((row) => row.evaluation.verdict === 'fail').length,
        core: rows.filter((row) => row.isCore).length,
        required: rows.filter((row) => row.required).length,
      }
    })
    .sort((a, b) => {
      const ai = CATEGORY_ORDER.indexOf(a.category)
      const bi = CATEGORY_ORDER.indexOf(b.category)
      if (ai === -1 && bi === -1) return a.category.localeCompare(b.category)
      if (ai === -1) return 1
      if (bi === -1) return -1
      return ai - bi
    })
})

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

const verdictBadge = computed<{ label: string; tone: BadgeTone }>(() => {
  switch (verdictAggregate.value) {
    case 'SHIP':
      return { label: 'SHIP', tone: 'success' }
    case 'FIX':
      return { label: 'FIX', tone: 'warning' }
    case 'BLOCK':
      return { label: 'BLOCK', tone: 'danger' }
    default:
      return { label: 'unscored', tone: 'neutral' }
  }
})

function verdictTone(verdict: string): BadgeTone {
  if (verdict === 'pass') return 'success'
  if (verdict === 'partial') return 'warning'
  if (verdict === 'fail') return 'danger'
  return 'neutral'
}

function groupOpen(group: EvaluationGroup): boolean {
  return group.fail > 0 || group.partial > 0
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
      <UiBadge
        :tone="verdictBadge.tone"
        size="md"
        data-testid="cs-eeat-verdict"
      >
        verdict: {{ verdictBadge.label }}
      </UiBadge>
    </div>

    <div
      v-if="vetoesFailed.length > 0"
      class="rounded-md border border-danger-border bg-danger-subtle p-3 text-danger-fg"
      role="alert"
      data-testid="cs-eeat-veto-banner"
    >
      <strong>Cannot ship — veto item failed.</strong>
      <p class="mt-1 text-sm">
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
        class="rounded-md border border-default bg-bg-surface p-3 shadow-xs"
      >
        <div class="text-xs uppercase text-fg-muted">
          {{ dim }}
        </div>
        <div class="mt-1 text-2xl font-semibold">
          {{ Math.round(report.score.dimension_scores[dim]) }}
        </div>
        <div class="mt-2 h-2 w-full overflow-hidden rounded bg-bg-sunken">
          <div
            class="h-full"
            :class="
              report.score.dimension_scores[dim] >= 70
                ? 'bg-success'
                : report.score.dimension_scores[dim] >= 50
                  ? 'bg-warning'
                  : 'bg-danger'
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
        class="rounded-md border border-default bg-bg-surface p-3 shadow-xs"
      >
        <div class="flex items-baseline justify-between">
          <span class="text-sm font-medium text-fg-muted">{{ name }}</span>
          <span class="text-2xl font-semibold">{{ Math.round(score) }}</span>
        </div>
      </div>
    </div>

    <div
      v-if="report && evaluationGroups.length > 0"
      class="space-y-2"
      aria-label="EEAT evaluation groups"
    >
      <details
        v-for="group in evaluationGroups"
        :key="group.category"
        class="rounded-md border border-default bg-bg-surface shadow-xs"
        :open="groupOpen(group)"
      >
        <summary class="cursor-pointer px-4 py-3 marker:text-fg-subtle">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 class="text-sm font-semibold text-fg-strong">
                {{ group.category }} · {{ group.title }}
              </h3>
              <p class="mt-0.5 text-xs text-fg-muted">
                {{ group.description }}
              </p>
            </div>
            <div class="flex flex-wrap items-center gap-1.5">
              <UiBadge tone="neutral">
                {{ group.rows.length }} checks
              </UiBadge>
              <UiBadge
                v-if="group.core > 0"
                tone="danger"
              >
                {{ group.core }} core
              </UiBadge>
              <UiBadge
                v-if="group.required > 0"
                tone="warning"
              >
                {{ group.required }} required
              </UiBadge>
              <UiBadge
                v-if="group.fail > 0"
                tone="danger"
              >
                {{ group.fail }} fail
              </UiBadge>
              <UiBadge
                v-else-if="group.partial > 0"
                tone="warning"
              >
                {{ group.partial }} partial
              </UiBadge>
              <UiBadge
                v-else
                tone="success"
              >
                all pass
              </UiBadge>
            </div>
          </div>
        </summary>
        <div class="border-t border-subtle">
          <div class="grid grid-cols-[120px_120px_1fr] border-b border-subtle px-4 py-2 text-xs font-semibold uppercase text-fg-muted">
            <div>Criterion</div>
            <div>Verdict</div>
            <div>Notes</div>
          </div>
          <div
            v-for="row in group.rows"
            :key="row.evaluation.id"
            class="grid grid-cols-[120px_120px_1fr] gap-3 border-b border-subtle px-4 py-2 text-sm last:border-b-0"
          >
            <div class="flex flex-wrap items-center gap-1">
              <span class="font-mono text-xs text-fg-strong">{{ row.code }}</span>
              <UiBadge
                v-if="row.isCore"
                tone="danger"
                data-testid="cs-eeat-core-badge"
              >
                core
              </UiBadge>
              <UiBadge
                v-else-if="row.required"
                tone="warning"
              >
                required
              </UiBadge>
            </div>
            <div>
              <UiBadge :tone="verdictTone(row.evaluation.verdict)">
                {{ row.evaluation.verdict }}
              </UiBadge>
            </div>
            <p class="text-fg-muted">
              {{ row.evaluation.notes ?? '—' }}
            </p>
          </div>
        </div>
      </details>
    </div>

    <p
      v-if="!loading && report && report.evaluations.length === 0"
      class="rounded-md border border-dashed border-subtle bg-bg-surface px-5 py-8 text-center text-sm text-fg-muted"
    >
      No EEAT evaluations recorded yet for this article. Agent EEAT gate output will appear here after the quality step runs.
    </p>
  </section>
</template>
