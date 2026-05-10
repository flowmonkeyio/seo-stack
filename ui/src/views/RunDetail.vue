<script setup lang="ts">
// RunDetail — single-run audit view with steps + children timeline.
//
// Per audit M-29 + PLAN.md L603. The wire shape exposes:
//   - `GET /api/v1/runs/{id}`            → RunOut (no inline steps)
//   - `GET /api/v1/runs/{id}/children`   → list of child RunOut rows
//   - `GET /api/v1/procedures/runs/{id}` → {run, steps[]} (procedure runs only)
//
// IMPORTANT: there is NO `GET /api/v1/runs/{id}/steps` endpoint — `run_steps`
// + `run_step_calls` are surfaced inline only for procedure-kind runs via
// the procedures endpoint. PLAN.md L603 says the run get returns "step list
// with run_steps + run_step_calls" but the M2 implementation only exposes
// the run row itself. The view falls back to:
//   - procedure-kind runs → procedure_run_steps (rich, has output_json)
//   - other kinds        → metadata_json + the children panel
// Documented in the M5.C report quality concerns.

import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import KvList from '@/components/KvList.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  UiButton,
  UiCallout,
  UiEmptyState,
  UiJsonBlock,
  UiPanel,
  UiSectionHeader,
} from '@/components/ui'
import { useRunsStore, type Run } from '@/stores/runs'
import { useToastsStore } from '@/stores/toasts'
import type { ProcedureRunStep } from '@/stores/procedures'

const props = defineProps<{
  runId: number
  projectId: number
}>()

const runsStore = useRunsStore()
const toasts = useToastsStore()

const run = ref<Run | null>(null)
const children = ref<Run[]>([])
const procedureSteps = ref<ProcedureRunStep[]>([])
const expandedStep = ref<number | null>(null)
const loading = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    run.value = await runsStore.get(props.runId)
    const [kids, proc] = await Promise.all([
      runsStore.children(props.runId),
      runsStore.getProcedureRunSteps(props.runId),
    ])
    children.value = kids
    procedureSteps.value = proc?.steps ?? []
  } catch (err) {
    toasts.error('Failed to load run', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

interface KvItem {
  key: string
  label: string
  value: unknown
}

const summary = computed<KvItem[]>(() => {
  if (!run.value) return []
  return [
    { key: 'id', label: 'Run id', value: `#${run.value.id}` },
    { key: 'kind', label: 'Kind', value: run.value.kind },
    { key: 'status', label: 'Status', value: run.value.status },
    { key: 'started', label: 'Started', value: new Date(run.value.started_at).toLocaleString() },
    {
      key: 'ended',
      label: 'Ended',
      value: run.value.ended_at ? new Date(run.value.ended_at).toLocaleString() : '—',
    },
    { key: 'duration', label: 'Duration', value: durationOf(run.value) },
    {
      key: 'parent',
      label: 'Parent',
      value: run.value.parent_run_id !== null ? `#${run.value.parent_run_id}` : '—',
    },
    { key: 'last_step', label: 'Last step', value: run.value.last_step ?? '—' },
    { key: 'procedure_slug', label: 'Procedure slug', value: run.value.procedure_slug ?? '—' },
    { key: 'error', label: 'Error', value: run.value.error ?? '—' },
  ]
})

const metadataKv = computed<KvItem[]>(() => {
  if (!run.value?.metadata_json) return []
  const meta = run.value.metadata_json as Record<string, unknown>
  return Object.entries(meta).map(([k, v]) => ({ key: k, label: k, value: v }))
})

function durationOf(r: Run): string {
  if (!r.ended_at) return r.status === 'running' ? 'running…' : '—'
  const ms = new Date(r.ended_at).getTime() - new Date(r.started_at).getTime()
  const s = Math.round(ms / 1000)
  return s < 60 ? `${s}s` : `${Math.round(s / 60)}m`
}

async function abort(cascade = true): Promise<void> {
  try {
    const updated = await runsStore.abort(props.runId, cascade)
    run.value = updated
    toasts.success('Run aborted', cascade ? 'cascaded to children' : '')
  } catch (err) {
    toasts.error('Abort failed', err instanceof Error ? err.message : undefined)
  }
}

async function heartbeat(): Promise<void> {
  try {
    const updated = await runsStore.heartbeat(props.runId)
    if (updated) run.value = updated
    toasts.success('Heartbeat sent')
  } catch (err) {
    toasts.error('Heartbeat failed', err instanceof Error ? err.message : undefined)
  }
}

function toggleStep(idx: number): void {
  expandedStep.value = expandedStep.value === idx ? null : idx
}

onMounted(load)
watch(() => props.runId, load)
</script>

<template>
  <UiEmptyState
    v-if="loading && !run"
    :title="`Loading run #${runId}`"
    description="Fetching run metadata, children, and procedure steps."
    size="md"
  />
  <UiEmptyState
    v-else-if="!run"
    title="Run not found"
    :description="`Run #${runId} is not available in the local daemon.`"
    size="md"
  />
  <div
    v-else
    class="space-y-4"
  >
    <UiPanel
      aria-labelledby="cs-run-summary-title"
      class="p-4"
    >
      <UiSectionHeader
        id="cs-run-summary-title"
        title="Summary"
      >
        <template #actions>
          <UiButton
            v-if="run.status === 'running'"
            size="sm"
            variant="secondary"
            @click="heartbeat"
          >
            Heartbeat
          </UiButton>
          <UiButton
            v-if="run.status === 'running'"
            size="sm"
            variant="danger"
            @click="abort(true)"
          >
            Abort (cascade)
          </UiButton>
          <StatusBadge
            :status="run.status"
            kind="run"
          />
        </template>
      </UiSectionHeader>
      <KvList
        :items="summary"
        :two-column="true"
      />
    </UiPanel>

    <UiPanel
      v-if="metadataKv.length > 0"
      aria-labelledby="cs-run-metadata-title"
      class="p-4"
    >
      <UiSectionHeader
        id="cs-run-metadata-title"
        title="Metadata"
      />
      <KvList :items="metadataKv" />
    </UiPanel>

    <UiPanel
      aria-labelledby="cs-run-steps-title"
      class="p-4"
    >
      <UiSectionHeader
        id="cs-run-steps-title"
        title="Steps timeline"
      />
      <UiCallout
        v-if="procedureSteps.length === 0"
        tone="info"
        density="compact"
      >
        Per-step grain (run_steps + run_step_calls) is exposed via
        <code>/api/v1/procedures/runs/{id}</code> for procedure-kind runs. Skill-run
        steps surface in M7 once the procedure runner records them. Use the
        children panel below to drill into nested runs.
      </UiCallout>
      <ol
        v-else
        class="space-y-2"
      >
        <li
          v-for="(step, idx) in procedureSteps"
          :key="step.id"
          class="rounded-md border border-default bg-bg-surface"
        >
          <button
            type="button"
            class="focus-ring flex w-full items-center justify-between gap-3 p-3 text-left text-sm hover:bg-bg-surface-alt"
            :aria-expanded="expandedStep === idx"
            :aria-controls="`cs-run-step-panel-${idx}`"
            @click="toggleStep(idx)"
          >
            <span class="flex flex-wrap items-center gap-2">
              <span class="font-mono text-xs text-fg-muted">
                #{{ step.step_index }}
              </span>
              <span class="font-medium text-fg-default">{{ step.step_id }}</span>
              <StatusBadge
                :status="step.status"
                kind="job"
                :small="true"
              />
            </span>
            <span class="text-xs text-fg-muted">
              {{ step.started_at ? new Date(step.started_at).toLocaleTimeString() : 'pending' }}
              {{ step.ended_at ? '→ ' + new Date(step.ended_at).toLocaleTimeString() : '' }}
              <span aria-hidden="true">{{ expandedStep === idx ? '▴' : '▾' }}</span>
            </span>
          </button>
          <div
            v-if="expandedStep === idx"
            :id="`cs-run-step-panel-${idx}`"
            class="border-t border-subtle bg-bg-surface-alt p-3 text-xs"
          >
            <UiCallout
              v-if="step.error"
              tone="danger"
              density="compact"
              class="mb-2"
            >
              {{ step.error }}
            </UiCallout>
            <div v-if="step.output_json && Object.keys(step.output_json).length > 0">
              <h3 class="mb-1 font-semibold">
                output_json
              </h3>
              <UiJsonBlock
                :data="step.output_json"
                density="compact"
                max-height="16rem"
              />
            </div>
            <p
              v-else
              class="text-fg-muted"
            >
              No output recorded.
            </p>
          </div>
        </li>
      </ol>
    </UiPanel>

    <UiPanel
      aria-labelledby="cs-run-children-title"
      class="p-4"
    >
      <UiSectionHeader
        id="cs-run-children-title"
        title="Children runs"
      />
      <p
        v-if="children.length === 0"
        class="text-sm text-fg-muted"
      >
        No child runs.
      </p>
      <ul
        v-else
        class="space-y-1 text-sm"
      >
        <li
          v-for="c in children"
          :key="c.id"
          class="flex items-center justify-between rounded-sm border border-default bg-bg-surface p-2"
        >
          <RouterLink
            :to="`/projects/${projectId}/runs/${c.id}`"
            class="text-fg-link hover:underline"
          >
            #{{ c.id }} · {{ c.kind }}
          </RouterLink>
          <StatusBadge
            :status="c.status"
            kind="run"
            :small="true"
          />
        </li>
      </ul>
    </UiPanel>
  </div>
</template>
