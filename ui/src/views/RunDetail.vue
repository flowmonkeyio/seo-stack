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
  <div
    v-if="loading && !run"
    class="rounded border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400"
  >
    Loading run #{{ runId }}…
  </div>
  <div
    v-else-if="!run"
    class="rounded border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400"
  >
    Run not found.
  </div>
  <div
    v-else
    class="space-y-6"
  >
    <section
      class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900"
      aria-labelledby="cs-run-summary-title"
    >
      <div class="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2
          id="cs-run-summary-title"
          class="text-base font-semibold"
        >
          Summary
        </h2>
        <div class="flex gap-2">
          <button
            v-if="run.status === 'running'"
            type="button"
            class="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            @click="heartbeat"
          >
            Heartbeat
          </button>
          <button
            v-if="run.status === 'running'"
            type="button"
            class="rounded border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900/30"
            @click="abort(true)"
          >
            Abort (cascade)
          </button>
          <StatusBadge
            :status="run.status"
            kind="run"
          />
        </div>
      </div>
      <KvList
        :items="summary"
        :two-column="true"
      />
    </section>

    <section
      v-if="metadataKv.length > 0"
      class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900"
      aria-labelledby="cs-run-metadata-title"
    >
      <h2
        id="cs-run-metadata-title"
        class="mb-3 text-base font-semibold"
      >
        Metadata
      </h2>
      <KvList :items="metadataKv" />
    </section>

    <section
      class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900"
      aria-labelledby="cs-run-steps-title"
    >
      <h2
        id="cs-run-steps-title"
        class="mb-3 text-base font-semibold"
      >
        Steps timeline
      </h2>
      <p
        v-if="procedureSteps.length === 0"
        class="rounded border border-blue-200 bg-blue-50 p-2 text-xs text-blue-800 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-200"
      >
        Per-step grain (run_steps + run_step_calls) is exposed via
        <code>/api/v1/procedures/runs/{id}</code> for procedure-kind runs. Skill-run
        steps surface in M7 once the procedure runner records them. Use the
        children panel below to drill into nested runs.
      </p>
      <ol
        v-else
        class="space-y-2"
      >
        <li
          v-for="(step, idx) in procedureSteps"
          :key="step.id"
          class="rounded border border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/60"
        >
          <button
            type="button"
            class="flex w-full items-center justify-between gap-3 p-3 text-left text-sm hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:hover:bg-gray-800"
            :aria-expanded="expandedStep === idx"
            :aria-controls="`cs-run-step-panel-${idx}`"
            @click="toggleStep(idx)"
          >
            <span class="flex flex-wrap items-center gap-2">
              <span class="font-mono text-xs text-gray-500 dark:text-gray-400">
                #{{ step.step_index }}
              </span>
              <span class="font-medium">{{ step.step_id }}</span>
              <StatusBadge
                :status="step.status"
                kind="job"
                :small="true"
              />
            </span>
            <span class="text-xs text-gray-500 dark:text-gray-400">
              {{ step.started_at ? new Date(step.started_at).toLocaleTimeString() : 'pending' }}
              {{ step.ended_at ? '→ ' + new Date(step.ended_at).toLocaleTimeString() : '' }}
              <span aria-hidden="true">{{ expandedStep === idx ? '▴' : '▾' }}</span>
            </span>
          </button>
          <div
            v-if="expandedStep === idx"
            :id="`cs-run-step-panel-${idx}`"
            class="border-t border-gray-200 bg-white p-3 text-xs dark:border-gray-700 dark:bg-gray-900"
          >
            <div
              v-if="step.error"
              class="mb-2 rounded bg-red-50 p-2 text-xs text-red-700 dark:bg-red-900/30 dark:text-red-200"
            >
              {{ step.error }}
            </div>
            <div v-if="step.output_json && Object.keys(step.output_json).length > 0">
              <h3 class="mb-1 font-semibold">
                output_json
              </h3>
              <pre class="overflow-x-auto rounded bg-gray-100 p-2 font-mono text-[11px] dark:bg-gray-800">{{ JSON.stringify(step.output_json, null, 2) }}</pre>
            </div>
            <p
              v-else
              class="text-gray-500 dark:text-gray-400"
            >
              No output recorded.
            </p>
          </div>
        </li>
      </ol>
    </section>

    <section
      class="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-900"
      aria-labelledby="cs-run-children-title"
    >
      <h2
        id="cs-run-children-title"
        class="mb-3 text-base font-semibold"
      >
        Children runs
      </h2>
      <p
        v-if="children.length === 0"
        class="text-sm text-gray-600 dark:text-gray-400"
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
          class="flex items-center justify-between rounded border border-gray-200 p-2 dark:border-gray-700"
        >
          <RouterLink
            :to="`/projects/${projectId}/runs/${c.id}`"
            class="text-blue-700 hover:underline dark:text-blue-300"
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
    </section>
  </div>
</template>
