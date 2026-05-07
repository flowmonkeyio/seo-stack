<script setup lang="ts">
// BriefTab — render `articles.brief_json` as structured KvList + JSON editor.
//
// Per PLAN.md L408-L424 the brief carries voice_id, primary_kw, secondary_kws,
// target_word_count, intent, audience, outline_hint_md, research_summary,
// compliance_jurisdictions, schema_types — all flat keys.
//
// "Edit" mode swaps to a JSON editor textarea; saving calls
// `articlesStore.setBrief({expected_etag, brief_json})`.

import { computed, ref, watch } from 'vue'

import KvList from '@/components/KvList.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import { useArticlesStore, ArticleEtagError } from '@/stores/articles'
import { useToastsStore } from '@/stores/toasts'

const props = defineProps<{
  articleId: number
}>()

const articlesStore = useArticlesStore()
const toasts = useToastsStore()

const article = computed(() => articlesStore.currentDetail)
const briefJson = computed<Record<string, unknown>>(() => {
  const j = article.value?.brief_json
  if (j && typeof j === 'object') return j as Record<string, unknown>
  return {}
})

const editing = ref(false)
const draftText = ref('')
const saving = ref(false)
const parseError = ref<string | null>(null)

function startEdit(): void {
  draftText.value = JSON.stringify(briefJson.value, null, 2)
  parseError.value = null
  editing.value = true
}

function cancelEdit(): void {
  if (saving.value) return
  editing.value = false
  parseError.value = null
}

async function saveEdit(): Promise<void> {
  if (saving.value || !article.value) return
  let parsed: Record<string, unknown>
  try {
    parsed = JSON.parse(draftText.value || '{}') as Record<string, unknown>
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      throw new SyntaxError('expected an object')
    }
  } catch (err) {
    parseError.value = err instanceof Error ? err.message : 'invalid JSON'
    return
  }
  const etag = article.value.step_etag
  if (!etag) {
    toasts.error('Article has no step_etag', 'Reload the article and try again.')
    return
  }
  saving.value = true
  try {
    await articlesStore.setBrief(props.articleId, {
      expected_etag: etag,
      brief_json: parsed,
    })
    toasts.success('Brief saved')
    editing.value = false
  } catch (err) {
    if (err instanceof ArticleEtagError) {
      toasts.error('Stale article version', 'Reload the article and retry.')
    } else {
      toasts.error('Save failed', err instanceof Error ? err.message : undefined)
    }
  } finally {
    saving.value = false
  }
}

// Resync the draft text whenever the article changes underneath us.
watch(
  () => article.value?.brief_json,
  () => {
    if (editing.value) return
    draftText.value = JSON.stringify(briefJson.value, null, 2)
  },
  { immediate: true },
)

const items = computed(() => {
  const j = briefJson.value
  return Object.keys(j).map((k) => ({ key: k, label: k, value: j[k] }))
})
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-brief-tab-title"
  >
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2
        id="cs-brief-tab-title"
        class="text-base font-semibold"
      >
        Brief
      </h2>
      <div class="flex gap-2">
        <button
          v-if="!editing"
          type="button"
          class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
          @click="startEdit"
        >
          Edit
        </button>
        <template v-else>
          <button
            type="button"
            class="rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800"
            :disabled="saving"
            @click="cancelEdit"
          >
            Cancel
          </button>
          <button
            type="button"
            class="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            :disabled="saving"
            @click="saveEdit"
          >
            {{ saving ? 'Saving…' : 'Save brief' }}
          </button>
        </template>
      </div>
    </div>

    <div v-if="!editing">
      <p
        v-if="items.length === 0"
        class="rounded border border-dashed border-gray-300 p-4 text-sm text-gray-600 dark:border-gray-700 dark:text-gray-300"
      >
        Brief not yet written. Click <strong>Edit</strong> to compose one.
      </p>
      <KvList
        v-else
        :items="items"
      >
        <template
          v-for="key in items.map((i) => i.key)"
          :key="key"
          #[`item:${key}`]="{ value }"
        >
          <span
            v-if="value === null || value === undefined"
            class="text-gray-500"
          >—</span>
          <span
            v-else-if="Array.isArray(value)"
            class="font-mono text-xs"
          >
            {{ (value as unknown[]).map((v) => String(v)).join(', ') }}
          </span>
          <MarkdownView
            v-else-if="typeof value === 'string' && (key.endsWith('_md') || key === 'research_summary' || key === 'outline_hint_md')"
            :source="value as string"
          />
          <span v-else-if="typeof value === 'string'">{{ value }}</span>
          <span v-else-if="typeof value === 'number' || typeof value === 'boolean'">{{ String(value) }}</span>
          <pre
            v-else
            class="overflow-x-auto rounded bg-gray-50 p-2 font-mono text-xs dark:bg-gray-800"
          >{{ JSON.stringify(value, null, 2) }}</pre>
        </template>
      </KvList>
    </div>

    <div v-else>
      <label
        class="block text-sm"
      >
        <span class="font-medium">Brief JSON</span>
        <textarea
          v-model="draftText"
          rows="20"
          spellcheck="false"
          class="mt-1 w-full rounded border border-gray-300 bg-white p-3 font-mono text-xs leading-snug text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
          aria-label="Brief JSON editor"
        />
      </label>
      <p
        v-if="parseError"
        class="mt-1 rounded bg-red-50 p-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200"
        role="alert"
      >
        Invalid JSON: {{ parseError }}
      </p>
    </div>
  </section>
</template>
