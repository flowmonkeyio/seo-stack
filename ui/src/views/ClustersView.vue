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

import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import {
  UiButton,
  UiCallout,
  UiDialog,
  UiEmptyState,
  UiPageShell,
  UiPanel,
  UiSectionHeader,
} from '@/components/ui'
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
  pillar: 'bg-eeat-subtle text-eeat-fg',
  spoke: 'bg-info-subtle text-info-fg',
  hub: 'bg-warning-subtle text-warning-fg',
  comparison: 'bg-success-subtle text-success-fg',
  resource: 'bg-neutral-subtle text-neutral-fg',
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  await clustersStore.refresh(projectId.value)
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <UiPageShell>
    <ProjectPageHeader
      :project-id="projectId"
      title="Clusters"
      description="Shape topical architecture with pillar, spoke, hub, comparison, and resource clusters."
      :breadcrumbs="[{ label: 'Clusters' }]"
    >
      <template #actions>
        <UiButton
          variant="primary"
          @click="openCreate(null)"
        >
          New cluster
        </UiButton>
      </template>
    </ProjectPageHeader>

    <UiCallout
      v-if="error"
      tone="danger"
    >
      {{ error }}
    </UiCallout>

    <UiEmptyState
      v-if="empty"
      title="No clusters yet"
      description="Create a pillar first, then add spokes, hubs, comparison, or resource pages underneath it."
      size="lg"
    >
      <template #actions>
        <UiButton
          variant="primary"
          @click="openCreate(null)"
        >
          Create cluster
        </UiButton>
      </template>
    </UiEmptyState>

    <div
      v-else
      :class="[
        'grid gap-6',
        selected ? 'lg:grid-cols-[1fr_22rem]' : 'lg:grid-cols-1',
      ]"
    >
      <ul
        class="divide-y divide-border-subtle rounded-md border border-default bg-bg-surface shadow-xs"
        :aria-busy="loading"
      >
        <li
          v-for="row in flatRows"
          :key="row.node.id"
          class="flex flex-wrap items-center justify-between gap-3 px-3 py-2 hover:bg-bg-surface-alt"
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
              class="text-fg-subtle"
            >└</span>
            <span class="font-medium text-fg-default">{{ row.node.name }}</span>
            <span
              :class="['rounded-full px-2 py-0.5 text-xs font-medium', TYPE_BADGE[row.node.type] ?? TYPE_BADGE.resource]"
            >
              {{ row.node.type }}
            </span>
            <span
              v-if="row.node.children.length > 0"
              class="text-xs text-fg-muted"
            >
              {{ row.node.children.length }} child{{ row.node.children.length === 1 ? '' : 'ren' }}
            </span>
          </button>
          <div class="flex gap-1">
            <button
              type="button"
              class="focus-ring rounded-sm border border-default px-2 py-0.5 text-xs text-fg-default hover:bg-bg-surface-alt"
              :aria-label="`Add child cluster under ${row.node.name}`"
              @click="openCreate(row.node)"
            >
              + child
            </button>
          </div>
        </li>
      </ul>

      <UiPanel
        v-if="selected"
        class="p-4"
        aria-labelledby="cs-cluster-side-title"
      >
        <UiSectionHeader
          id="cs-cluster-side-title"
          :title="selected.name"
        >
          <template #actions>
            <UiButton
              size="sm"
              variant="secondary"
              aria-label="Close cluster panel"
              @click="closeSidePanel"
            >
              Close
            </UiButton>
          </template>
        </UiSectionHeader>

        <dl class="mb-3 grid gap-1 text-sm">
          <div class="flex justify-between">
            <dt class="text-fg-muted">
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
            <dt class="text-fg-muted">
              Parent
            </dt>
            <dd>{{ selected.parent_id ? clustersStore.getById(selected.parent_id)?.name ?? '—' : '—' }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-fg-muted">
              Created
            </dt>
            <dd>{{ new Date(selected.created_at).toLocaleString() }}</dd>
          </div>
        </dl>

        <UiSectionHeader
          title="Topics in this cluster"
          as="h3"
        />
        <p
          v-if="sidePanelTopicsLoading"
          class="text-sm text-fg-muted"
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
            class="rounded-sm border border-default bg-bg-surface px-2 py-1 text-sm"
          >
            <div class="font-medium">
              {{ t.title }}
            </div>
            <div class="text-xs text-fg-muted">
              {{ t.status }} · {{ t.intent }}
            </div>
          </li>
        </ul>
        <p
          v-else
          class="text-sm text-fg-muted"
        >
          No topics in this cluster yet.
        </p>
      </UiPanel>
    </div>

    <UiDialog
      :model-value="showCreate"
      title="New cluster"
      description="Create a pillar cluster or add a child cluster under an existing pillar."
      size="md"
      @update:model-value="(open: boolean) => open ? showCreate = true : closeCreate()"
    >
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
      </form>
      <template #footer>
        <UiButton
          variant="secondary"
          :disabled="submitting"
          @click="closeCreate"
        >
          Cancel
        </UiButton>
        <UiButton
          variant="primary"
          :loading="submitting"
          @click="submitCreate"
        >
          Create cluster
        </UiButton>
      </template>
    </UiDialog>
  </UiPageShell>
</template>
