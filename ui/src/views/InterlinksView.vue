<script setup lang="ts">
// InterlinksView — internal-link graph + suggest/apply/dismiss/repair flow.
//
// Wires to the interlinks Pinia store. Heavy bulk-actions UX per audit M-31.
//
// Status pill bar drives the `status` filter (server-side). Filter bar
// adds from/to article narrowing (server-side) + a score-min slider that
// filters client-side because the wire shape doesn't expose a score.
// "Suggest" calls /interlinks/suggest with an empty payload — the daemon
// wraps the underlying ranker in M5/M7 — which lands suggestions for the
// project. "Repair" iterates known articles and reflows broken links.

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  UiBulkActionBar,
  UiButton,
  UiCallout,
  UiDialog,
  UiEmptyState,
  UiPageShell,
  UiSegmentedControl,
} from '@/components/ui'
import { useInterlinksStore, type InternalLink } from '@/stores/interlinks'
import { useArticlesStore } from '@/stores/articles'
import { useToastsStore } from '@/stores/toasts'
import { InternalLinkStatus as InternalLinkStatusEnum } from '@/api'
import type { DataTableColumn } from '@/components/types'

const route = useRoute()
const router = useRouter()
const interlinksStore = useInterlinksStore()
const articlesStore = useArticlesStore()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const { filteredItems, loading, nextCursor, error, filters } = storeToRefs(interlinksStore)

const selection = ref<Set<number>>(new Set())
const bulkPending = ref(false)
const repairOpen = ref(false)
const repairArticleId = ref<number | null>(null)
const repairPending = ref(false)
const detailOpen = ref<InternalLink | null>(null)

const STATUS_OPTIONS: { key: 'all' | `${InternalLinkStatusEnum}`; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'suggested', label: 'Suggested' },
  { key: 'applied', label: 'Applied' },
  { key: 'dismissed', label: 'Dismissed' },
  { key: 'broken', label: 'Broken' },
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

function setSort(key: string): void {
  interlinksStore.setSort(key as 'id' | '-id' | 'created_at' | '-created_at')
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

async function suggestMore(): Promise<void> {
  // The daemon's `suggest` endpoint accepts a list of {from,to,anchor,position}
  // rows. M5.C surfaces the operator-driven suggest shape: we POST with an
  // empty list which the repository interprets as a no-op idempotent call.
  // Once the M7 interlinker skill ships it will populate this list with
  // ML-ranked candidates. The button still works pre-M7 — it just adds zero
  // rows and reloads the table.
  try {
    await interlinksStore.suggest(projectId.value, [])
    toasts.success('Suggestions updated')
    await interlinksStore.refresh(projectId.value)
  } catch (err) {
    toasts.error('Failed to suggest', err instanceof Error ? err.message : undefined)
  }
}

async function applyOne(row: InternalLink): Promise<void> {
  try {
    await interlinksStore.apply(projectId.value, row.id)
    toasts.success('Interlink applied', `${row.anchor_text}`)
  } catch (err) {
    toasts.error('Apply failed', err instanceof Error ? err.message : undefined)
  }
}

async function dismissOne(row: InternalLink): Promise<void> {
  try {
    await interlinksStore.dismiss(projectId.value, row.id)
    toasts.success('Interlink dismissed', `${row.anchor_text}`)
  } catch (err) {
    toasts.error('Dismiss failed', err instanceof Error ? err.message : undefined)
  }
}

async function applySelected(): Promise<void> {
  if (selection.value.size === 0) return
  bulkPending.value = true
  try {
    const ids = Array.from(selection.value)
    await interlinksStore.bulkApply(projectId.value, ids)
    toasts.success('Bulk apply', `${ids.length} interlinks applied`)
    selection.value = new Set()
  } catch (err) {
    toasts.error('Bulk apply failed', err instanceof Error ? err.message : undefined)
  } finally {
    bulkPending.value = false
  }
}

async function dismissSelected(): Promise<void> {
  if (selection.value.size === 0) return
  bulkPending.value = true
  try {
    let success = 0
    for (const id of selection.value) {
      try {
        await interlinksStore.dismiss(projectId.value, id)
        success++
      } catch {
        // single-row failure surfaces in toast at end
      }
    }
    toasts.success('Bulk dismiss', `${success}/${selection.value.size} dismissed`)
    selection.value = new Set()
  } finally {
    bulkPending.value = false
  }
}

function openRepair(): void {
  repairOpen.value = true
  repairArticleId.value = null
}

async function submitRepair(): Promise<void> {
  if (!repairArticleId.value) {
    toasts.error('Article required', 'Pick an article to repair links for.')
    return
  }
  repairPending.value = true
  try {
    const rows = await interlinksStore.repair(projectId.value, repairArticleId.value)
    toasts.success('Repair complete', `${rows.length} links flipped to broken`)
    repairOpen.value = false
    await interlinksStore.refresh(projectId.value)
  } catch (err) {
    toasts.error('Repair failed', err instanceof Error ? err.message : undefined)
  } finally {
    repairPending.value = false
  }
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

const empty = computed<boolean>(
  () => !loading.value && filteredItems.value.length === 0 && selection.value.size === 0,
)

onMounted(load)
watch(projectId, load)
</script>

<template>
  <UiPageShell>
    <ProjectPageHeader
      :project-id="projectId"
      title="Interlinks"
      description="Review suggested links, apply approved anchors, dismiss weak matches, and repair broken internal links."
      :breadcrumbs="[{ label: 'Interlinks' }]"
    >
      <template #actions>
        <UiButton
          variant="secondary"
          @click="openRepair"
        >
          Repair
        </UiButton>
        <UiButton
          variant="primary"
          @click="suggestMore"
        >
          Suggest interlinks
        </UiButton>
      </template>
    </ProjectPageHeader>

    <UiCallout
      v-if="error"
      tone="danger"
    >
      {{ error }}
    </UiCallout>

    <UiSegmentedControl
      :model-value="filters.status ?? 'all'"
      :options="STATUS_OPTIONS"
      label="Interlink status filter"
      @select="onStatusSelect"
    />

    <div class="flex flex-wrap items-center gap-3 text-sm">
      <label class="flex items-center gap-2">
        <span class="text-fg-muted">From article</span>
        <select
          :value="filters.from_article_id !== null ? String(filters.from_article_id) : ''"
          class="h-8 rounded-sm border border-default bg-bg-surface px-2 text-sm text-fg-default focus-ring"
          aria-label="Filter from article"
          @change="setFromFilter(($event.target as HTMLSelectElement).value)"
        >
          <option value="">
            All
          </option>
          <option
            v-for="a in articlesStore.items"
            :key="a.id"
            :value="a.id"
          >
            {{ a.title }}
          </option>
        </select>
      </label>
      <label class="flex items-center gap-2">
        <span class="text-fg-muted">To article</span>
        <select
          :value="filters.to_article_id !== null ? String(filters.to_article_id) : ''"
          class="h-8 rounded-sm border border-default bg-bg-surface px-2 text-sm text-fg-default focus-ring"
          aria-label="Filter to article"
          @change="setToFilter(($event.target as HTMLSelectElement).value)"
        >
          <option value="">
            All
          </option>
          <option
            v-for="a in articlesStore.items"
            :key="a.id"
            :value="a.id"
          >
            {{ a.title }}
          </option>
        </select>
      </label>
      <label class="flex items-center gap-2">
        <span class="text-fg-muted">Score min</span>
        <input
          :value="filters.score_min"
          type="range"
          min="0"
          max="1"
          step="0.05"
          class="w-32"
          aria-label="Score minimum"
          @input="setScoreMin(Number.parseFloat(($event.target as HTMLInputElement).value))"
        >
        <span class="w-8 text-right text-xs text-fg-muted">{{ filters.score_min.toFixed(2) }}</span>
      </label>
      <label class="flex items-center gap-2">
        <span class="text-fg-muted">Sort</span>
        <select
          :value="interlinksStore.sort"
          class="h-8 rounded-sm border border-default bg-bg-surface px-2 text-sm text-fg-default focus-ring"
          aria-label="Sort"
          @change="setSort(($event.target as HTMLSelectElement).value)"
        >
          <option value="-id">
            score desc
          </option>
          <option value="id">
            score asc
          </option>
          <option value="-created_at">
            created desc
          </option>
          <option value="created_at">
            created asc
          </option>
        </select>
      </label>
    </div>

    <UiBulkActionBar
      v-if="selection.size > 0"
      :count="selection.size"
      aria-label="Selected interlinks"
      @clear="selection = new Set()"
    >
      <UiButton
        size="sm"
        variant="secondary"
        :disabled="bulkPending"
        @click="applySelected"
      >
        Apply selected
      </UiButton>
      <UiButton
        size="sm"
        variant="secondary"
        :disabled="bulkPending"
        @click="dismissSelected"
      >
        Dismiss selected
      </UiButton>
    </UiBulkActionBar>

    <UiEmptyState
      v-if="empty"
      title="No interlinks yet"
      description="Generate suggestions from the current article set, then apply or dismiss them from the table."
      size="lg"
    >
      <template #actions>
        <UiButton
          variant="primary"
          @click="suggestMore"
        >
          Suggest interlinks
        </UiButton>
      </template>
    </UiEmptyState>

    <DataTable
      v-if="!empty"
      :items="filteredItems"
      :columns="columns"
      :loading="loading"
      :next-cursor="nextCursor"
      :selection="selection"
      aria-label="Interlinks"
      empty-message="No interlinks match the filters"
      @row-click="openDetail"
      @selection-change="(next: Set<number>) => selection = new Set(next)"
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
        <div class="flex items-center gap-2">
          <StatusBadge
            :status="(row as InternalLink).status"
            kind="interlink"
          />
          <UiButton
            v-if="(row as InternalLink).status === 'suggested'"
            size="sm"
            variant="secondary"
            :aria-label="`Apply interlink ${(row as InternalLink).id}`"
            @click.stop="applyOne(row as InternalLink)"
          >
            Apply
          </UiButton>
          <UiButton
            v-if="(row as InternalLink).status === 'suggested'"
            size="sm"
            variant="secondary"
            :aria-label="`Dismiss interlink ${(row as InternalLink).id}`"
            @click.stop="dismissOne(row as InternalLink)"
          >
            Dismiss
          </UiButton>
        </div>
      </template>
    </DataTable>

    <UiDialog
      :model-value="repairOpen"
      title="Repair interlinks"
      description="Mark all live interlinks pointing at the selected article as broken."
      size="md"
      @update:model-value="(open: boolean) => repairOpen = open"
    >
      <UiCallout
        tone="info"
        density="compact"
        class="mb-3"
      >
        Use this after unpublishing or deleting an article so dangling links surface in the broken filter.
      </UiCallout>
      <label class="mb-3 block text-sm">
        <span class="font-medium">Article</span>
        <select
          v-model="repairArticleId"
          class="mt-1 w-full rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
        >
          <option :value="null">
            — pick an article —
          </option>
          <option
            v-for="a in articlesStore.items"
            :key="a.id"
            :value="a.id"
          >
            {{ a.title }}
          </option>
        </select>
      </label>
      <template #footer>
        <UiButton
          variant="secondary"
          :disabled="repairPending"
          @click="repairOpen = false"
        >
          Cancel
        </UiButton>
        <UiButton
          variant="primary"
          :loading="repairPending"
          @click="submitRepair"
        >
          Repair links
        </UiButton>
      </template>
    </UiDialog>

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
            <dd>{{ detailOpen.position ?? '—' }}</dd>
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
        <UiCallout
          tone="info"
          density="compact"
          class="mt-3"
        >
          Surrounding paragraph context lands in M7 alongside the interlinker
          skill. M5.C displays the anchor + endpoints only.
        </UiCallout>
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
