<script setup lang="ts">
// VersionsTab — `article_versions` rows + side-by-side diff against current.
//
// Diff strategy: simple line-based diff (LCS-ish via JS Set comparisons).
// Adequate for human review of refresh-detector deltas; not a full
// diff-match-patch engine. Avoids adding a new npm dependency for D8 parity.

import { computed, onMounted, ref, watch } from 'vue'

import DataTable from '@/components/DataTable.vue'
import { useArticlesStore, type ArticleVersion } from '@/stores/articles'
import { useToastsStore } from '@/stores/toasts'
import type { DataTableColumn } from '@/components/types'

const props = defineProps<{
  articleId: number
}>()

const articlesStore = useArticlesStore()
const toasts = useToastsStore()

const versions = ref<ArticleVersion[]>([])
const loading = ref(false)
const compareTo = ref<ArticleVersion | null>(null)

const columns: DataTableColumn<ArticleVersion>[] = [
  { key: 'version', label: 'Version' },
  {
    key: 'created_at',
    label: 'Created',
    format: (v) => (v ? new Date(String(v)).toLocaleString() : ''),
  },
  { key: 'refresh_reason', label: 'Refresh reason' },
]

async function load(): Promise<void> {
  loading.value = true
  try {
    versions.value = await articlesStore.listVersions(props.articleId)
  } catch (err) {
    toasts.error('Failed to load versions', err instanceof Error ? err.message : undefined)
  } finally {
    loading.value = false
  }
}

async function snapshotNow(): Promise<void> {
  try {
    await articlesStore.createVersion(props.articleId)
    toasts.success('Version snapshot created')
    await load()
  } catch (err) {
    toasts.error('Snapshot failed', err instanceof Error ? err.message : undefined)
  }
}

interface DiffLine {
  kind: 'context' | 'added' | 'removed'
  text: string
}

const currentBody = computed<string>(() => articlesStore.currentDetail?.edited_md ?? '')

function diffLines(a: string, b: string): DiffLine[] {
  const aLines = a.split('\n')
  const bLines = b.split('\n')
  const aSet = new Set(aLines)
  const bSet = new Set(bLines)
  const out: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < aLines.length || j < bLines.length) {
    if (i >= aLines.length) {
      out.push({ kind: 'added', text: bLines[j] })
      j++
    } else if (j >= bLines.length) {
      out.push({ kind: 'removed', text: aLines[i] })
      i++
    } else if (aLines[i] === bLines[j]) {
      out.push({ kind: 'context', text: aLines[i] })
      i++
      j++
    } else if (!bSet.has(aLines[i])) {
      out.push({ kind: 'removed', text: aLines[i] })
      i++
    } else if (!aSet.has(bLines[j])) {
      out.push({ kind: 'added', text: bLines[j] })
      j++
    } else {
      // Both lines exist on the other side but at different positions; emit
      // the more-likely one first.
      out.push({ kind: 'removed', text: aLines[i] })
      i++
    }
  }
  return out
}

const diffComputed = computed<DiffLine[]>(() => {
  if (!compareTo.value) return []
  const oldText = compareTo.value.edited_md ?? ''
  return diffLines(oldText, currentBody.value)
})

function startCompare(v: ArticleVersion): void {
  compareTo.value = v
}

function clearCompare(): void {
  compareTo.value = null
}

onMounted(load)
watch(() => props.articleId, load)
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-versions-tab-title"
  >
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2
        id="cs-versions-tab-title"
        class="text-base font-semibold"
      >
        Versions
      </h2>
      <button
        type="button"
        class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
        @click="snapshotNow"
      >
        Snapshot now
      </button>
    </div>

    <DataTable
      :items="versions"
      :columns="columns"
      :loading="loading"
      aria-label="Article versions"
      empty-message="No versions yet."
    >
      <template #cell:version="{ row }">
        <button
          type="button"
          class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          @click="startCompare(row as ArticleVersion)"
        >
          v{{ (row as ArticleVersion).version }} — compare to current
        </button>
      </template>
    </DataTable>

    <div
      v-if="compareTo"
      class="rounded border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-900"
    >
      <div class="mb-2 flex items-baseline justify-between">
        <h3 class="text-sm font-semibold">
          Diff: v{{ compareTo.version }} → current
        </h3>
        <button
          type="button"
          class="rounded border border-gray-300 px-2 py-0.5 text-xs hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          @click="clearCompare"
        >
          Clear diff
        </button>
      </div>
      <pre
        tabindex="0"
        class="max-h-96 overflow-auto rounded bg-gray-50 p-2 font-mono text-xs leading-snug dark:bg-gray-800"
      ><span
        v-for="(line, idx) in diffComputed"
        :key="idx"
        :class="
          line.kind === 'added'
            ? 'block bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200'
            : line.kind === 'removed'
              ? 'block bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200'
              : 'block'
        "
      >{{ line.kind === 'added' ? '+ ' : line.kind === 'removed' ? '- ' : '  ' }}{{ line.text }}</span></pre>
    </div>
  </section>
</template>
