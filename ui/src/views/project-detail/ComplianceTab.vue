<script setup lang="ts">
// ComplianceTab — read-only compliance rule visibility.

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import {
  UiBadge,
  UiButton,
  UiFormField,
  UiSectionHeader,
  UiSelect,
} from '@/components/ui'
import { apiFetch, formatApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import { CompliancePosition, ComplianceRuleKind, type components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type Rule = components['schemas']['ComplianceRuleOut']

const route = useRoute()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))
const rules = ref<Rule[]>([])
const loading = ref(false)
const selectedRuleId = ref<number | null>(null)

const filterKind = ref<string>('')
const filterPosition = ref<string>('')

const kindSelectOptions = computed(() => [
  { value: '', label: 'All kinds' },
  ...Object.values(ComplianceRuleKind).map((kind) => ({ value: kind, label: kind })),
])
const positionSelectOptions = computed(() => [
  { value: '', label: 'All positions' },
  ...Object.values(CompliancePosition).map((position) => ({ value: position, label: position })),
])

const filteredRules = computed<Rule[]>(() => {
  return rules.value.filter((rule) => {
    if (filterKind.value && rule.kind !== filterKind.value) return false
    if (filterPosition.value && rule.position !== filterPosition.value) return false
    return true
  })
})
const activeRules = computed(() => rules.value.filter((rule) => rule.is_active))
const selectedRule = computed(() => {
  return (
    rules.value.find((rule) => rule.id === selectedRuleId.value) ??
    filteredRules.value[0] ??
    rules.value[0] ??
    null
  )
})

const columns: DataTableColumn<Rule>[] = [
  { key: 'title', label: 'Title' },
  { key: 'kind', label: 'Kind' },
  { key: 'position', label: 'Position' },
  { key: 'is_active', label: 'Status', format: (value) => (value ? 'Active' : 'Inactive') },
]

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  loading.value = true
  try {
    const res = await apiFetch<Rule[]>(`/api/v1/projects/${projectId.value}/compliance`)
    rules.value = Array.isArray(res) ? res : []
    if (selectedRuleId.value && !rules.value.some((rule) => rule.id === selectedRuleId.value)) {
      selectedRuleId.value = null
    }
  } catch (err) {
    toasts.error('Failed to load compliance rules', formatApiError(err))
  } finally {
    loading.value = false
  }
}

function selectRule(rule: Rule): void {
  selectedRuleId.value = rule.id
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <section class="space-y-6">
    <UiSectionHeader
      title="Compliance rules"
      description="Read-only rule inventory used by agent procedures when disclosure or policy blocks are needed."
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

    <div class="grid gap-3 md:grid-cols-3">
      <div class="rounded-md border border-default bg-bg-surface p-3 shadow-xs">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          Rules
        </p>
        <p class="mt-2 text-sm font-semibold text-fg-strong">
          {{ rules.length }}
        </p>
        <p class="mt-1 text-xs text-fg-muted">
          Total disclosure and policy rules.
        </p>
      </div>
      <div class="rounded-md border border-default bg-bg-surface p-3 shadow-xs">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          Active
        </p>
        <p class="mt-2 text-sm font-semibold text-fg-strong">
          {{ activeRules.length }}
        </p>
        <p class="mt-1 text-xs text-fg-muted">
          Rules eligible for agent insertion.
        </p>
      </div>
      <div class="rounded-md border border-default bg-bg-surface p-3 shadow-xs">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          Filtered
        </p>
        <p class="mt-2 text-sm font-semibold text-fg-strong">
          {{ filteredRules.length }}
        </p>
        <p class="mt-1 text-xs text-fg-muted">
          Rows matching the current view filters.
        </p>
      </div>
    </div>

    <div
      v-if="rules.length > 0"
      class="rounded-md border border-subtle bg-bg-surface p-3"
    >
      <div class="grid gap-3 md:grid-cols-[16rem_16rem_1fr]">
        <UiFormField label="Filter by kind">
          <UiSelect
            v-model="filterKind"
            :options="kindSelectOptions"
          />
        </UiFormField>
        <UiFormField label="Filter by position">
          <UiSelect
            v-model="filterPosition"
            :options="positionSelectOptions"
          />
        </UiFormField>
        <div class="flex items-end justify-end">
          <UiBadge tone="neutral">
            {{ filteredRules.length }} shown
          </UiBadge>
        </div>
      </div>
    </div>

    <div
      v-if="!loading && rules.length === 0"
      class="rounded-md border border-dashed border-subtle bg-bg-surface px-4 py-8 text-center"
    >
      <p class="text-sm font-semibold text-fg-strong">
        No compliance rules
      </p>
      <p class="mt-1 text-sm text-fg-muted">
        Agent-owned rules will appear here with kind, placement, jurisdictions, and body text.
      </p>
    </div>

    <div
      v-else
      class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,0.75fr)]"
    >
      <DataTable
        :items="filteredRules"
        :columns="columns"
        :loading="loading"
        empty-message="No compliance rules match these filters."
        aria-label="Compliance rules"
        @row-click="selectRule"
      >
        <template #cell:is_active="{ row }">
          <UiBadge :tone="(row as Rule).is_active ? 'success' : 'warning'">
            {{ (row as Rule).is_active ? 'Active' : 'Inactive' }}
          </UiBadge>
        </template>
      </DataTable>

      <aside class="rounded-md border border-default bg-bg-surface p-4 shadow-xs">
        <div
          v-if="selectedRule"
          class="space-y-4"
        >
          <header class="space-y-2">
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="text-sm font-semibold text-fg-strong">
                {{ selectedRule.title }}
              </h3>
              <UiBadge :tone="selectedRule.is_active ? 'success' : 'warning'">
                {{ selectedRule.is_active ? 'Active' : 'Inactive' }}
              </UiBadge>
            </div>
            <dl class="grid gap-2 text-xs text-fg-muted sm:grid-cols-3">
              <div>
                <dt class="font-semibold uppercase tracking-wide text-fg-subtle">
                  Kind
                </dt>
                <dd class="mt-1">
                  {{ selectedRule.kind }}
                </dd>
              </div>
              <div>
                <dt class="font-semibold uppercase tracking-wide text-fg-subtle">
                  Position
                </dt>
                <dd class="mt-1">
                  {{ selectedRule.position }}
                </dd>
              </div>
              <div>
                <dt class="font-semibold uppercase tracking-wide text-fg-subtle">
                  Jurisdictions
                </dt>
                <dd class="mt-1">
                  {{ selectedRule.jurisdictions || 'Any' }}
                </dd>
              </div>
            </dl>
          </header>

          <div v-if="selectedRule.body_md?.trim()">
            <p class="mb-2 text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
              Body markdown
            </p>
            <MarkdownView
              :source="selectedRule.body_md"
            />
          </div>
          <div
            v-else
            class="rounded-md border border-dashed border-subtle bg-bg-surface-alt p-4 text-sm text-fg-muted"
          >
            No body markdown is recorded for this rule.
          </div>
        </div>
        <p
          v-else
          class="text-sm text-fg-muted"
        >
          Select a rule to inspect its contents.
        </p>
      </aside>
    </div>
  </section>
</template>
