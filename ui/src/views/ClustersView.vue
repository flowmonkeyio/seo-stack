<script setup lang="ts">
// ClustersView — read-only pillar/spoke hierarchy + side-panel detail.

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'

import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import {
  UiButton,
  UiCallout,
  UiEmptyState,
  UiPageShell,
  UiPanel,
  UiSectionHeader,
} from '@/components/ui'
import { ClusterType as ClusterTypeEnum } from '@/api'
import { useClustersStore } from '@/stores/clusters'
import { useTopicsStore } from '@/stores/topics'
import type { Cluster, ClusterTreeNode } from '@/stores/clusters'

const route = useRoute()
const clustersStore = useClustersStore()
const topicsStore = useTopicsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { tree, loading, error, items } = storeToRefs(clustersStore)
const selected = ref<Cluster | null>(null)
const sidePanelTopicsLoading = ref(false)

interface FlatRow {
  depth: number
  node: ClusterTreeNode
}

const flatRows = computed<FlatRow[]>(() => {
  const out: FlatRow[] = []
  function walk(nodes: ClusterTreeNode[], depth: number): void {
    for (const node of nodes) {
      out.push({ depth, node })
      if (node.children.length > 0) walk(node.children, depth + 1)
    }
  }
  walk(tree.value, 0)
  return out
})

const empty = computed<boolean>(() => !loading.value && items.value.length === 0)

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

const TYPE_BADGE = {
  [ClusterTypeEnum.pillar]: 'bg-eeat-subtle text-eeat-fg',
  [ClusterTypeEnum.spoke]: 'bg-info-subtle text-info-fg',
  [ClusterTypeEnum.hub]: 'bg-warning-subtle text-warning-fg',
  [ClusterTypeEnum.comparison]: 'bg-success-subtle text-success-fg',
  [ClusterTypeEnum.resource]: 'bg-neutral-subtle text-neutral-fg',
} satisfies {
  [Type in ClusterTypeEnum]: string
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
      description="Inspect topical architecture across pillar, spoke, hub, comparison, and resource clusters."
      :breadcrumbs="[{ label: 'Clusters' }]"
    />

    <UiCallout
      v-if="error"
      tone="danger"
    >
      {{ error }}
    </UiCallout>

    <UiEmptyState
      v-if="empty"
      title="No clusters yet"
      description="Clusters appear here after agent topical mapping runs."
      size="lg"
    />

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
            >-</span>
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
            <dd>{{ selected.parent_id ? clustersStore.getById(selected.parent_id)?.name ?? '-' : '-' }}</dd>
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
            v-for="topic in topicsStore.items"
            :key="topic.id"
            class="rounded-sm border border-default bg-bg-surface px-2 py-1 text-sm"
          >
            <div class="font-medium">
              {{ topic.title }}
            </div>
            <div class="text-xs text-fg-muted">
              {{ topic.status }} / {{ topic.intent }}
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
  </UiPageShell>
</template>
