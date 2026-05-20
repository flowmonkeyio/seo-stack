<script setup lang="ts">
// InterlinksView — read-only internal-link graph.

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  UiButton,
  UiCallout,
  UiDialog,
  UiFormField,
  UiPageShell,
  UiPanel,
  UiRange,
  UiSegmentedControl,
  UiSelect,
} from '@/components/ui'
import { InternalLinkStatus as InternalLinkStatusEnum } from '@/api'
import { useArticlesStore } from '@/stores/articles'
import { useInterlinksStore, type InternalLink } from '@/stores/interlinks'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const router = useRouter()
const interlinksStore = useInterlinksStore()
const articlesStore = useArticlesStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { filteredItems, loading, nextCursor, error, filters } = storeToRefs(interlinksStore)
const detailOpen = ref<InternalLink | null>(null)

const STATUS_OPTIONS: { key: 'all' | `${InternalLinkStatusEnum}`; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'suggested', label: 'Suggested' },
  { key: 'applied', label: 'Applied' },
  { key: 'dismissed', label: 'Dismissed' },
  { key: 'broken', label: 'Broken' },
]

const articleOptions = computed(() => [
  { value: '', label: 'All articles' },
  ...articlesStore.items.map((article) => ({ value: article.id, label: article.title })),
])

const SORT_OPTIONS = [
  { value: '-id', label: 'Score desc' },
  { value: 'id', label: 'Score asc' },
  { value: '-created_at', label: 'Created desc' },
  { value: 'created_at', label: 'Created asc' },
]

const columns: DataTableColumn<InternalLink>[] = [
  { key: 'from_article_id', label: 'From article' },
  { key: 'anchor_text', label: 'Anchor' },
  { key: 'to_article_id', label: 'To article' },
  { key: 'position', label: 'Position', widthClass: 'w-20' },
  { key: 'status', label: 'Status' },
]

function setStatusFilter(opt: 'all' | `${InternalLinkStatusEnum}`): void {
  interlinksStore.setFilter('status', opt === 'all' ? null : (opt as InternalLinkStatusEnum))
  void interlinksStore.refresh(projectId.value)
}

function onStatusSelect(key: string | number): void {
  setStatusFilter(String(key) as 'all' | `${InternalLinkStatusEnum}`)
}

function setFromFilter(value: string): void {
  interlinksStore.setFilter('from_article_id', value === '' ? null : Number.parseInt(value, 10))
  void interlinksStore.refresh(projectId.value)
}

function setToFilter(value: string): void {
  interlinksStore.setFilter('to_article_id', value === '' ? null : Number.parseInt(value, 10))
  void interlinksStore.refresh(projectId.value)
}

function setScoreMin(value: number): void {
  interlinksStore.setFilter('score_min', value)
}

function onFromFilterChange(value: string | number | null): void {
  setFromFilter(value === null ? '' : String(value))
}

function onToFilterChange(value: string | number | null): void {
  setToFilter(value === null ? '' : String(value))
}

function setSort(key: string | number | null): void {
  if (key === null) return
  interlinksStore.setSort(String(key) as 'id' | '-id' | 'created_at' | '-created_at')
}

function articleTitle(id: number): string {
  return articlesStore.getById(id)?.title ?? `#${id}`
}

async function loadMore(): Promise<void> {
  await interlinksStore.loadMore(projectId.value)
}

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  interlinksStore.reset()
  await Promise.all([
    interlinksStore.refresh(projectId.value),
    articlesStore.items.length === 0
      ? articlesStore.refresh(projectId.value)
      : Promise.resolve(),
  ])
}

function openDetail(row: InternalLink): void {
  detailOpen.value = row
}

function closeDetail(): void {
  detailOpen.value = null
}

function gotoArticle(id: number): void {
  void router.push(`/projects/${projectId.value}/articles/${id}`)
}

const empty = computed<boolean>(() => !loading.value && filteredItems.value.length === 0)

onMounted(load)
watch(projectId, load)
</script>

<template>
  <UiPageShell>
    <ProjectPageHeader
      :project-id="projectId"
      title="Interlinks"
      description="Inspect suggested, applied, dismissed, and broken internal links."
      :breadcrumbs="[{ label: 'Interlinks' }]"
    />

    <UiCallout
      v-if="error"
      tone="danger"
    >
      {{ error }}
    </UiCallout>

    <UiPanel
      aria-label="Interlink filters"
      class="p-4"
    >
      <UiSegmentedControl
        :model-value="filters.status ?? 'all'"
        :options="STATUS_OPTIONS"
        label="Interlink status filter"
        @select="onStatusSelect"
      />

      <div class="mt-3 grid gap-3 lg:grid-cols-[1fr_1fr_220px_180px]">
        <UiFormField label="From article">
          <UiSelect
            :model-value="filters.from_article_id ?? ''"
            :options="articleOptions"
            @change="onFromFilterChange"
          />
        </UiFormField>
        <UiFormField label="To article">
          <UiSelect
            :model-value="filters.to_article_id ?? ''"
            :options="articleOptions"
            @change="onToFilterChange"
          />
        </UiFormField>
        <UiFormField label="Score min">
          <UiRange
            :model-value="filters.score_min"
            :min="0"
            :max="1"
            :step="0.05"
            :format="(value) => value.toFixed(2)"
            aria-label="Score minimum"
            @update:model-value="setScoreMin"
          />
        </UiFormField>
        <UiFormField label="Sort">
          <UiSelect
            :model-value="interlinksStore.sort"
            :options="SORT_OPTIONS"
            @change="setSort"
          />
        </UiFormField>
      </div>
    </UiPanel>

    <div
      v-if="empty"
      class="rounded-md border border-dashed border-subtle bg-bg-surface px-6 py-10 text-center"
    >
      <h2 class="text-sm font-semibold text-fg-strong">
        No interlinks yet
      </h2>
      <p class="mt-1 text-sm text-fg-muted">
        Agent interlinker suggestions will appear here with source article, target article, anchor, and status.
      </p>
    </div>

    <DataTable
      v-if="!empty"
      :items="filteredItems"
      :columns="columns"
      :loading="loading"
      :next-cursor="nextCursor"
      aria-label="Interlinks"
      empty-message="No interlinks match the filters"
      @row-click="openDetail"
      @load-more="loadMore"
    >
      <template #cell:from_article_id="{ row }">
        <button
          type="button"
          class="focus-ring rounded-xs text-fg-link hover:underline"
          @click.stop="gotoArticle((row as InternalLink).from_article_id)"
        >
          {{ articleTitle((row as InternalLink).from_article_id) }}
        </button>
      </template>
      <template #cell:to_article_id="{ row }">
        <button
          type="button"
          class="focus-ring rounded-xs text-fg-link hover:underline"
          @click.stop="gotoArticle((row as InternalLink).to_article_id)"
        >
          {{ articleTitle((row as InternalLink).to_article_id) }}
        </button>
      </template>
      <template #cell:status="{ row }">
        <StatusBadge
          :status="(row as InternalLink).status"
          kind="interlink"
        />
      </template>
    </DataTable>

    <UiDialog
      :model-value="detailOpen !== null"
      :title="detailOpen ? `Interlink #${detailOpen.id}` : 'Interlink'"
      size="md"
      @update:model-value="(open: boolean) => open ? undefined : closeDetail()"
    >
      <template v-if="detailOpen">
        <dl class="space-y-2 text-sm">
          <div>
            <dt class="font-medium text-fg-muted">
              From
            </dt>
            <dd>{{ articleTitle(detailOpen.from_article_id) }}</dd>
          </div>
          <div>
            <dt class="font-medium text-fg-muted">
              To
            </dt>
            <dd>{{ articleTitle(detailOpen.to_article_id) }}</dd>
          </div>
          <div>
            <dt class="font-medium text-fg-muted">
              Anchor text
            </dt>
            <dd class="font-mono">
              {{ detailOpen.anchor_text }}
            </dd>
          </div>
          <div>
            <dt class="font-medium text-fg-muted">
              Position
            </dt>
            <dd>{{ detailOpen.position ?? '-' }}</dd>
          </div>
          <div>
            <dt class="font-medium text-fg-muted">
              Status
            </dt>
            <dd>
              <StatusBadge
                :status="detailOpen.status"
                kind="interlink"
              />
            </dd>
          </div>
        </dl>
      </template>
      <template #footer>
        <UiButton
          variant="secondary"
          @click="closeDetail"
        >
          Close
        </UiButton>
      </template>
    </UiDialog>
  </UiPageShell>
</template>
