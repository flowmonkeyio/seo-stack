<script setup lang="ts">
// DraftTab — `articles.draft_md` editor with append/replace controls.
//
// PLAN.md L583 + audit B-07: each save carries fresh `expected_etag` from
// the prior response. The 100-sequential-set_draft path (skill #8 procedure)
// is the same code path — every save is one round-trip, server returns the
// fresh etag, store caches it, next save uses it.
//
// `?append=true|false` toggle: replace (default) overwrites the whole body;
// append concatenates the editor body onto the existing draft.

import { computed, ref, watch } from 'vue'

import MarkdownEditor from '@/components/MarkdownEditor.vue'
import { useArticlesStore, ArticleEtagError } from '@/stores/articles'
import { useToastsStore } from '@/stores/toasts'

const props = defineProps<{
  articleId: number
}>()

const articlesStore = useArticlesStore()
const toasts = useToastsStore()

const article = computed(() => articlesStore.currentDetail)

const value = ref<string>('')
const appendMode = ref(false)
const saving = ref(false)

watch(
  () => article.value?.draft_md,
  (next) => {
    if (!appendMode.value) value.value = next ?? ''
  },
  { immediate: true },
)

async function onSave(body: string): Promise<{ updated_at?: string }> {
  if (!article.value) return {}
  const etag = article.value.step_etag
  if (!etag) {
    toasts.error('Article has no step_etag', 'Reload the article and try again.')
    return {}
  }
  saving.value = true
  try {
    const row = await articlesStore.setDraft(
      props.articleId,
      { expected_etag: etag, draft_md: body },
      appendMode.value,
    )
    toasts.success(appendMode.value ? 'Draft appended' : 'Draft saved')
    if (appendMode.value) value.value = ''
    return { updated_at: row.updated_at }
  } catch (err) {
    if (err instanceof ArticleEtagError) {
      toasts.error('Stale article version', 'Reload the article and retry.')
    } else {
      toasts.error('Save failed', err instanceof Error ? err.message : undefined)
    }
    throw err
  } finally {
    saving.value = false
  }
}

async function markDrafted(): Promise<void> {
  if (!article.value) return
  const etag = article.value.step_etag
  if (!etag) return
  try {
    await articlesStore.markDrafted(props.articleId, { expected_etag: etag })
    toasts.success('Article marked drafted')
  } catch (err) {
    if (err instanceof ArticleEtagError) {
      toasts.error('Stale article version', 'Reload the article and retry.')
    } else {
      toasts.error('Mark drafted failed', err instanceof Error ? err.message : undefined)
    }
  }
}
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-draft-tab-title"
  >
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2
        id="cs-draft-tab-title"
        class="text-base font-semibold"
      >
        Draft
      </h2>
      <div class="flex items-center gap-2 text-sm">
        <label class="inline-flex items-center gap-1">
          <input
            v-model="appendMode"
            type="checkbox"
            class="h-4 w-4"
          >
          Append mode
        </label>
        <button
          v-if="article?.status === 'outlined'"
          type="button"
          class="rounded border border-emerald-300 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-800 hover:bg-emerald-100 dark:border-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200"
          @click="markDrafted"
        >
          Mark drafted
        </button>
      </div>
    </div>

    <p
      v-if="appendMode"
      class="rounded border border-blue-200 bg-blue-50 p-2 text-xs text-blue-800 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-200"
    >
      Saves will <strong>append</strong> to the existing draft. Use this for
      multi-section drafts where each save adds the next section.
    </p>

    <MarkdownEditor
      :value="value"
      :updated-at="article?.updated_at ?? null"
      :saving="saving"
      :on-save="onSave"
      aria-label="Article draft markdown editor"
      :placeholder="appendMode ? 'New section to append…' : '# Draft\n\nBody text here…'"
      @update:value="(v: string) => value = v"
    />
  </section>
</template>
