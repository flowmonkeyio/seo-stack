<script setup lang="ts">
// OutlineTab — markdown view + edit of `articles.outline_md`.

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
const saving = ref(false)

watch(
  () => article.value?.outline_md,
  (next) => {
    value.value = next ?? ''
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
    const row = await articlesStore.setOutline(props.articleId, {
      expected_etag: etag,
      outline_md: body,
    })
    toasts.success('Outline saved')
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
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-outline-tab-title"
  >
    <h2
      id="cs-outline-tab-title"
      class="text-base font-semibold"
    >
      Outline
    </h2>
    <MarkdownEditor
      :value="value"
      :updated-at="article?.updated_at ?? null"
      :saving="saving"
      :on-save="onSave"
      aria-label="Article outline markdown editor"
      :placeholder="'# Outline\n\n## Section 1\n…'"
      @update:value="(v: string) => value = v"
    />
  </section>
</template>
