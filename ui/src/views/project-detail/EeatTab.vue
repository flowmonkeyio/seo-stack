<script setup lang="ts">
// EeatTab — read-only EEAT rubric visibility.

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { UiBadge, UiButton, UiSectionHeader } from '@/components/ui'
import { apiFetch, formatApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'

type Criterion = components['schemas']['EeatCriterionOut']

const EEAT_CATEGORIES = ['E', 'EX', 'A', 'T', 'C', 'O', 'R'] as const
type EeatCategory = (typeof EEAT_CATEGORIES)[number]
type CriteriaByCategory = { [Category in EeatCategory]: Criterion[] }
type CategoryMeta = { title: string; description: string }
type CategoryStats = { total: number; core: number; required: number; active: number }

const route = useRoute()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const items = ref<Criterion[]>([])
const loading = ref(false)

const categoryMeta: Record<EeatCategory, CategoryMeta> = {
  E: {
    title: 'Experience',
    description: 'Original work, practical proof, and subject-matter depth.',
  },
  EX: {
    title: 'Expertise',
    description: 'Direct knowledge, reviewer quality, and specific methodology.',
  },
  A: {
    title: 'Authority',
    description: 'Recognized signals, authorship, mentions, and topical standing.',
  },
  T: {
    title: 'Trust',
    description: 'Policies, disclosures, security, and review transparency.',
  },
  C: {
    title: 'Coverage',
    description: 'Query coverage, structure, semantics, and answer completeness.',
  },
  O: {
    title: 'On-page',
    description: 'Formatting, schema, navigation, hierarchy, and page structure.',
  },
  R: {
    title: 'Reliability',
    description: 'Citations, freshness, consistency, links, and factual checks.',
  },
}

const grouped = computed(() => {
  const buckets: CriteriaByCategory = { E: [], EX: [], A: [], T: [], C: [], O: [], R: [] }
  for (const item of items.value) {
    const key = String(item.category)
    if (isEeatCategory(key)) buckets[key].push(item)
  }
  return buckets
})

const orderedCategories = computed<EeatCategory[]>(() =>
  EEAT_CATEGORIES.filter((category) => grouped.value[category].length > 0),
)
const coreCount = computed(() => items.value.filter((item) => item.tier === 'core').length)
const activeCount = computed(() => items.value.filter((item) => item.active).length)
const requiredCount = computed(() => items.value.filter((item) => item.required).length)

function isEeatCategory(value: string): value is EeatCategory {
  return (EEAT_CATEGORIES as readonly string[]).includes(value)
}

function isCore(criterion: Criterion): boolean {
  return criterion.tier === 'core'
}

function stateTone(value: boolean): 'success' | 'warning' {
  return value ? 'success' : 'warning'
}

function categoryStats(category: EeatCategory): CategoryStats {
  const rows = grouped.value[category]
  return {
    total: rows.length,
    core: rows.filter((item) => isCore(item)).length,
    required: rows.filter((item) => item.required).length,
    active: rows.filter((item) => item.active).length,
  }
}

function categoryOpen(category: EeatCategory): boolean {
  const stats = categoryStats(category)
  return stats.core > 0 || stats.required > 0
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  loading.value = true
  try {
    const res = await apiFetch<Criterion[]>(`/api/v1/projects/${projectId.value}/eeat`)
    items.value = Array.isArray(res) ? res : []
  } catch (err) {
    toasts.error('Failed to load EEAT criteria', formatApiError(err))
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <section class="space-y-6">
    <UiSectionHeader
      title="EEAT criteria"
      description="Read-only view of the quality rubric enforced by agent procedures before publishing."
    >
      <template #actions>
        <UiButton
          size="sm"
          variant="secondary"
          :disabled="loading"
          @click="load"
        >
          {{ loading ? 'Refreshing...' : 'Refresh' }}
        </UiButton>
      </template>
    </UiSectionHeader>

    <div class="rounded-md border border-subtle bg-bg-surface px-4 py-3 text-sm">
      <p class="font-semibold text-fg-strong">
        Agent-owned rubric
      </p>
      <p class="mt-0.5 text-fg-muted">
        This page shows the active rubric and core floor without changing project state.
      </p>
    </div>

    <div class="grid gap-3 md:grid-cols-4">
      <div class="rounded-md border border-default bg-bg-surface p-3 shadow-xs">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          Criteria
        </p>
        <p class="mt-2 text-sm font-semibold text-fg-strong">
          {{ items.length }}
        </p>
        <p class="mt-1 text-xs text-fg-muted">
          Total rubric checks.
        </p>
      </div>
      <div class="rounded-md border border-default bg-bg-surface p-3 shadow-xs">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          Core floor
        </p>
        <p class="mt-2 text-sm font-semibold text-fg-strong">
          {{ coreCount }}
        </p>
        <p class="mt-1 text-xs text-fg-muted">
          Non-negotiable criteria.
        </p>
      </div>
      <div class="rounded-md border border-default bg-bg-surface p-3 shadow-xs">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          Active
        </p>
        <p class="mt-2 text-sm font-semibold text-fg-strong">
          {{ activeCount }}
        </p>
        <p class="mt-1 text-xs text-fg-muted">
          Checks currently enforced.
        </p>
      </div>
      <div class="rounded-md border border-default bg-bg-surface p-3 shadow-xs">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          Required
        </p>
        <p class="mt-2 text-sm font-semibold text-fg-strong">
          {{ requiredCount }}
        </p>
        <p class="mt-1 text-xs text-fg-muted">
          Required for pass state.
        </p>
      </div>
    </div>

    <div
      v-if="loading"
      class="rounded-md border border-dashed border-default p-4 text-sm text-fg-muted"
    >
      Loading...
    </div>

    <div
      v-else-if="items.length === 0"
      class="rounded-md border border-dashed border-subtle bg-bg-surface px-4 py-8 text-center"
    >
      <p class="text-sm font-semibold text-fg-strong">
        No EEAT criteria
      </p>
      <p class="mt-1 text-sm text-fg-muted">
        Agent-owned criteria will appear here grouped by rubric area.
      </p>
    </div>

    <div
      v-else
      class="space-y-6"
    >
      <details
        v-for="cat in orderedCategories"
        :key="cat"
        class="overflow-hidden rounded-md border border-default bg-bg-surface shadow-xs"
        :open="categoryOpen(cat)"
      >
        <summary class="cursor-pointer px-4 py-3 marker:text-fg-subtle hover:bg-bg-surface-alt">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0">
              <h3 class="text-sm font-semibold text-fg-strong">
                {{ cat }} · {{ categoryMeta[cat].title }}
              </h3>
              <p class="mt-0.5 text-sm text-fg-muted">
                {{ categoryMeta[cat].description }}
              </p>
            </div>
            <div class="flex shrink-0 flex-wrap items-center gap-2">
              <UiBadge tone="neutral">
                {{ categoryStats(cat).total }} checks
              </UiBadge>
              <UiBadge
                v-if="categoryStats(cat).core > 0"
                tone="warning"
              >
                {{ categoryStats(cat).core }} core
              </UiBadge>
              <UiBadge
                v-if="categoryStats(cat).required > 0"
                tone="success"
              >
                {{ categoryStats(cat).required }} required
              </UiBadge>
              <span class="text-xs text-fg-muted">
                {{ categoryStats(cat).active }} active
              </span>
            </div>
          </div>
        </summary>
        <ul class="divide-y divide-default border-t border-subtle">
          <li
            v-for="criterion in grouped[cat]"
            :key="criterion.id"
            class="grid gap-3 px-4 py-3 lg:grid-cols-[minmax(0,1fr)_18rem]"
          >
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-mono text-xs text-fg-muted">
                  {{ criterion.code }}
                </span>
                <span class="font-medium text-fg-strong">{{ criterion.text }}</span>
                <UiBadge
                  v-if="isCore(criterion)"
                  tone="warning"
                >
                  Core
                </UiBadge>
              </div>
              <p class="mt-1 text-xs text-fg-muted">
                {{ criterion.description }}
              </p>
            </div>

            <div class="flex flex-wrap items-center gap-2 lg:justify-end">
              <UiBadge
                :tone="stateTone(criterion.required)"
                variant="outline"
              >
                {{ criterion.required ? 'Required' : 'Optional' }}
              </UiBadge>
              <UiBadge
                :tone="stateTone(criterion.active)"
                variant="outline"
              >
                {{ criterion.active ? 'Active' : 'Inactive' }}
              </UiBadge>
              <span
                class="rounded-sm border border-subtle px-2 py-1 font-mono text-xs text-fg-muted"
              >
                w={{ criterion.weight }}
              </span>
            </div>
          </li>
        </ul>
      </details>
    </div>
  </section>
</template>
