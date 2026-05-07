<script setup lang="ts">
// ClustersView — pillar/spoke hierarchy + create flow + side-panel detail.
//
// Wires to the clusters Pinia store. Tree rendering is a recursive
// component-less pattern using a flat list of (depth, node) tuples so we
// avoid recursive component hot reload churn (Vite HMR handles
// nested components but the tree depth is unbounded — flat traversal is
// O(n) with one pass). The PLAN's 5 cluster types are:
//   - pillar (top-level)
//   - spoke
//   - hub
//   - comparison
//   - resource
//
// Side panel: clicking a row opens a slide-in showing cluster details +
// the topics (filtered server-side on `cluster_id`) that belong to it.

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'

import { useClustersStore } from '@/stores/clusters'
import { useTopicsStore } from '@/stores/topics'
import { useToastsStore } from '@/stores/toasts'
import { ClusterType as ClusterTypeEnum } from '@/api'
import type { Cluster, ClusterTreeNode } from '@/stores/clusters'

const route = useRoute()
const clustersStore = useClustersStore()
const topicsStore = useTopicsStore()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { tree, loading, error, items } = storeToRefs(clustersStore)

const showCreate = ref(false)
const submitting = ref(false)

interface DraftCluster {
  name: string
  type: `${ClusterTypeEnum}`
  parent_id: number | null
}

const draft = ref<DraftCluster>(emptyDraft())

function emptyDraft(): DraftCluster {
  return { name: '', type: 'pillar', parent_id: null }
}

const pillarOptions = computed<Cluster[]>(() => items.value.filter((c) => c.type === 'pillar'))

const selected = ref<Cluster | null>(null)
const sidePanelTopicsLoading = ref(false)

interface FlatRow {
  depth: number
  node: ClusterTreeNode
}

const flatRows = computed<FlatRow[]>(() => {
  const out: FlatRow[] = []
  function walk(nodes: ClusterTreeNode[], depth: number): void {
    for (const n of nodes) {
      out.push({ depth, node: n })
      if (n.children.length > 0) walk(n.children, depth + 1)
    }
  }
  walk(tree.value, 0)
  return out
})

const empty = computed<boolean>(() => !loading.value && items.value.length === 0)

function openCreate(parent?: Cluster | null): void {
  draft.value = parent
    ? { name: '', type: 'spoke', parent_id: parent.id }
    : emptyDraft()
  showCreate.value = true
}

function closeCreate(): void {
  if (submitting.value) return
  showCreate.value = false
}

async function submitCreate(): Promise<void> {
  if (submitting.value) return
  if (!draft.value.name.trim()) {
    toasts.error('Missing required field', 'Name is required.')
    return
  }
  submitting.value = true
  try {
    const created = await clustersStore.create(projectId.value, {
      name: draft.value.name.trim(),
      type: draft.value.type as ClusterTypeEnum,
      parent_id: draft.value.parent_id,
    })
    toasts.success('Cluster created', created.name)
    showCreate.value = false
    selected.value = created
  } catch (err) {
    toasts.error(
      'Failed to create cluster',
      err instanceof Error ? err.message : undefined,
    )
  } finally {
    submitting.value = false
  }
}

async function selectCluster(cluster: Cluster): Promise<void> {
  selected.value = cluster
  sidePanelTopicsLoading.value = true
  try {
    topicsStore.setFilter('cluster_id', cluster.id)
    await topicsStore.refresh(projectId.value)
  } finally {
    sidePanelTopicsLoading.value = false
  }
}

function closeSidePanel(): void {
  selected.value = null
  topicsStore.setFilter('cluster_id', null)
}

const TYPE_BADGE: Record<string, string> = {
  pillar: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300',
  spoke: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  hub: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  comparison: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  resource: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300',
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  await clustersStore.refresh(projectId.value)
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <div class="mx-auto max-w-6xl">
    <header class="mb-4 flex flex-wrap items-baseline justify-between gap-3">
      <h1 class="text-2xl font-bold tracking-tight">
        Clusters
      </h1>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
        @click="openCreate(null)"
      >
        New cluster
      </button>
    </header>

    <p
      v-if="error"
      class="mb-3 rounded bg-red-50 p-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200"
    >
      {{ error }}
    </p>

    <div
      v-if="empty"
      class="rounded border border-dashed border-gray-300 p-8 text-center text-sm text-gray-600 dark:border-gray-700 dark:text-gray-300"
    >
      <p class="mb-2 text-base font-medium text-gray-900 dark:text-white">
        No clusters yet
      </p>
      <p class="mb-4">
        Pillars are top-level topical clusters; spokes / hubs / comparison /
        resource pages live underneath them. Create one to start the
        information architecture.
      </p>
      <button
        type="button"
        class="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        @click="openCreate(null)"
      >
        Create cluster
      </button>
    </div>

    <div
      v-else
      class="grid gap-6 lg:grid-cols-[1fr_22rem]"
    >
      <ul
        class="divide-y divide-gray-200 rounded border border-gray-200 dark:divide-gray-800 dark:border-gray-800"
        :aria-busy="loading"
      >
        <li
          v-for="row in flatRows"
          :key="row.node.id"
          class="flex flex-wrap items-center justify-between gap-3 px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-900"
          :style="{ paddingLeft: `${0.75 + row.depth * 1.25}rem` }"
        >
          <button
            type="button"
            class="flex flex-1 items-center gap-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
            :aria-expanded="selected?.id === row.node.id"
            @click="selectCluster(row.node)"
          >
            <span
              v-if="row.depth > 0"
              aria-hidden="true"
              class="text-gray-400"
            >└</span>
            <span class="font-medium">{{ row.node.name }}</span>
            <span
              :class="['rounded-full px-2 py-0.5 text-xs font-medium', TYPE_BADGE[row.node.type] ?? TYPE_BADGE.resource]"
            >
              {{ row.node.type }}
            </span>
            <span
              v-if="row.node.children.length > 0"
              class="text-xs text-gray-500 dark:text-gray-400"
            >
              {{ row.node.children.length }} child{{ row.node.children.length === 1 ? '' : 'ren' }}
            </span>
          </button>
          <div class="flex gap-1">
            <button
              type="button"
              class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
              :aria-label="`Add child cluster under ${row.node.name}`"
              @click="openCreate(row.node)"
            >
              + child
            </button>
          </div>
        </li>
      </ul>

      <aside
        v-if="selected"
        class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900"
        aria-labelledby="cs-cluster-side-title"
      >
        <div class="mb-3 flex items-baseline justify-between gap-2">
          <h2
            id="cs-cluster-side-title"
            class="text-base font-semibold"
          >
            {{ selected.name }}
          </h2>
          <button
            type="button"
            class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            aria-label="Close cluster panel"
            @click="closeSidePanel"
          >
            Close
          </button>
        </div>

        <dl class="mb-3 grid gap-1 text-sm">
          <div class="flex justify-between">
            <dt class="text-gray-600 dark:text-gray-400">
              Type
            </dt>
            <dd>
              <span
                :class="['rounded-full px-2 py-0.5 text-xs font-medium', TYPE_BADGE[selected.type] ?? TYPE_BADGE.resource]"
              >
                {{ selected.type }}
              </span>
            </dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-600 dark:text-gray-400">
              Parent
            </dt>
            <dd>{{ selected.parent_id ? clustersStore.getById(selected.parent_id)?.name ?? '—' : '—' }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-600 dark:text-gray-400">
              Created
            </dt>
            <dd>{{ new Date(selected.created_at).toLocaleString() }}</dd>
          </div>
        </dl>

        <h3 class="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-700 dark:text-gray-300">
          Topics in this cluster
        </h3>
        <p
          v-if="sidePanelTopicsLoading"
          class="text-sm text-gray-500"
        >
          Loading…
        </p>
        <ul
          v-else-if="topicsStore.items.length > 0"
          class="space-y-1"
        >
          <li
            v-for="t in topicsStore.items"
            :key="t.id"
            class="rounded border border-gray-200 px-2 py-1 text-sm dark:border-gray-800"
          >
            <div class="font-medium">
              {{ t.title }}
            </div>
            <div class="text-xs text-gray-600 dark:text-gray-400">
              {{ t.status }} · {{ t.intent }}
            </div>
          </li>
        </ul>
        <p
          v-else
          class="text-sm text-gray-500 dark:text-gray-400"
        >
          No topics in this cluster yet.
        </p>
      </aside>
    </div>

    <div
      v-if="showCreate"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cs-new-cluster-title"
      @click.self="closeCreate"
    >
      <div
        class="w-full max-w-md rounded-lg border border-gray-200 bg-white p-5 shadow-xl dark:border-gray-700 dark:bg-gray-900"
      >
        <h2
          id="cs-new-cluster-title"
          class="mb-3 text-lg font-semibold"
        >
          New cluster
        </h2>
        <form
          class="space-y-3"
          @submit.prevent="submitCreate"
        >
          <label class="block text-sm">
            <span class="font-medium">Name</span>
            <input
              v-model="draft.name"
              type="text"
              required
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
              autocomplete="off"
            >
          </label>
          <label class="block text-sm">
            <span class="font-medium">Type</span>
            <select
              v-model="draft.type"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            >
              <option value="pillar">
                pillar
              </option>
              <option value="spoke">
                spoke
              </option>
              <option value="hub">
                hub
              </option>
              <option value="comparison">
                comparison
              </option>
              <option value="resource">
                resource
              </option>
            </select>
          </label>
          <label class="block text-sm">
            <span class="font-medium">Parent (optional)</span>
            <select
              v-model="draft.parent_id"
              class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
            >
              <option :value="null">
                — none —
              </option>
              <option
                v-for="p in pillarOptions"
                :key="p.id"
                :value="p.id"
              >
                {{ p.name }}
              </option>
            </select>
          </label>
          <div class="mt-4 flex justify-end gap-2">
            <button
              type="button"
              class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
              :disabled="submitting"
              @click="closeCreate"
            >
              Cancel
            </button>
            <button
              type="submit"
              class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              :disabled="submitting"
            >
              {{ submitting ? 'Creating…' : 'Create cluster' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
