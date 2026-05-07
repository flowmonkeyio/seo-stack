<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { apiFetch, ApiError } from '@/lib/client'
import type { HealthResponse } from '@/api'

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string; status?: number }
  | { kind: 'loaded'; data: HealthResponse }

const state = ref<LoadState>({ kind: 'loading' })

async function load(): Promise<void> {
  state.value = { kind: 'loading' }
  try {
    const data = await apiFetch<HealthResponse>('/api/v1/health')
    state.value = { kind: 'loaded', data }
  } catch (err) {
    if (err instanceof ApiError) {
      state.value = { kind: 'error', message: err.message, status: err.status }
    } else if (err instanceof Error) {
      state.value = { kind: 'error', message: err.message }
    } else {
      state.value = { kind: 'error', message: 'Unknown error' }
    }
  }
}

onMounted(load)

const prettyJson = computed<string>(() => {
  if (state.value.kind !== 'loaded') return ''
  return JSON.stringify(state.value.data, null, 2)
})

const dbStatus = computed<string>(() => {
  if (state.value.kind !== 'loaded') return 'unknown'
  return String(state.value.data.db_status ?? 'unknown')
})

const dbBadgeClass = computed<string>(() => {
  const s = dbStatus.value.toLowerCase()
  if (s === 'ok' || s === 'ready' || s === 'healthy') {
    return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
  }
  if (s === 'unknown') {
    return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
  }
  return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
})

const schedulerRunning = computed<boolean | null>(() => {
  if (state.value.kind !== 'loaded') return null
  const v = state.value.data.scheduler_running
  return typeof v === 'boolean' ? v : null
})

const schedulerBadgeClass = computed<string>(() => {
  const v = schedulerRunning.value
  if (v === true)
    return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
  if (v === false) return 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
  return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
})

const schedulerLabel = computed<string>(() => {
  const v = schedulerRunning.value
  if (v === true) return 'running'
  if (v === false) return 'stopped'
  return 'unknown'
})
</script>

<template>
  <div class="mx-auto w-full max-w-2xl">
    <header class="mb-6">
      <h1 class="text-2xl font-bold tracking-tight sm:text-3xl">content-stack</h1>
      <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
        agent-driven SEO content pipelines
      </p>
    </header>

    <section
      class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:p-6 dark:border-gray-800 dark:bg-gray-900"
      aria-live="polite"
      :aria-busy="state.kind === 'loading'"
    >
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 class="text-base font-semibold sm:text-lg">Daemon health</h2>
        <button
          type="button"
          class="self-start rounded border border-gray-300 px-3 py-1 text-sm hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50 sm:self-auto dark:border-gray-700 dark:hover:bg-gray-800"
          :disabled="state.kind === 'loading'"
          @click="load"
        >
          Refresh
        </button>
      </div>

      <!-- Loading -->
      <div v-if="state.kind === 'loading'" class="mt-4 text-sm text-gray-500">
        Pinging <code>/api/v1/health</code>&hellip;
      </div>

      <!-- Error -->
      <div
        v-else-if="state.kind === 'error'"
        class="mt-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200"
        role="alert"
      >
        <div class="font-medium">Could not reach the daemon.</div>
        <div class="mt-1">
          <span v-if="state.status">HTTP {{ state.status }} &mdash; </span>{{ state.message }}
        </div>
        <div class="mt-2 text-xs opacity-80">
          Is the daemon running on <code>127.0.0.1:5180</code>? In dev,
          <code>pnpm dev</code> proxies <code>/api</code> to that origin.
        </div>
      </div>

      <!-- Loaded -->
      <div v-else class="mt-4 space-y-4">
        <div class="flex flex-wrap gap-2">
          <span
            class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
            :class="dbBadgeClass"
          >
            db: {{ dbStatus }}
          </span>
          <span
            class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
            :class="schedulerBadgeClass"
          >
            scheduler: {{ schedulerLabel }}
          </span>
          <span
            v-if="state.data.milestone"
            class="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-800 dark:bg-gray-800 dark:text-gray-200"
          >
            milestone: {{ state.data.milestone }}
          </span>
          <span
            v-if="state.data.version"
            class="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-800 dark:bg-gray-800 dark:text-gray-200"
          >
            v{{ state.data.version }}
          </span>
          <span
            v-if="typeof state.data.uptime_s === 'number'"
            class="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-800 dark:bg-gray-800 dark:text-gray-200"
          >
            uptime: {{ Math.round(state.data.uptime_s) }}s
          </span>
        </div>

        <pre
          class="max-h-80 overflow-auto rounded bg-gray-50 p-3 text-xs leading-relaxed text-gray-800 ring-1 ring-inset ring-gray-200 dark:bg-gray-950 dark:text-gray-200 dark:ring-gray-800"
          >{{ prettyJson }}</pre
        >
      </div>
    </section>

    <footer class="mt-6 text-xs text-gray-500 dark:text-gray-500">
      M0 scaffold &mdash; full views land in M6. See <code>PLAN.md</code> for sequencing.
    </footer>
  </div>
</template>
