<script setup lang="ts">
// DraftTab — read-only draft markdown.

import { computed } from 'vue'

import MarkdownView from '@/components/MarkdownView.vue'
import { useArticlesStore } from '@/stores/articles'

const articlesStore = useArticlesStore()
const article = computed(() => articlesStore.currentDetail)
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-draft-tab-title"
  >
    <div>
      <h2
        id="cs-draft-tab-title"
        class="text-base font-semibold text-fg-strong"
      >
        Draft
      </h2>
      <p class="mt-1 text-sm text-fg-muted">
        Draft assembly is agent-owned. The UI only displays the current draft artifact.
      </p>
    </div>

    <div
      v-if="!article?.draft_md?.trim()"
      class="rounded-md border border-dashed border-subtle bg-bg-surface px-5 py-8 text-center"
    >
      <h3 class="text-sm font-semibold text-fg-strong">
        No draft yet
      </h3>
      <p class="mt-1 text-sm text-fg-muted">
        The draft artifact will appear here after the agent completes draft assembly.
      </p>
    </div>

    <div
      v-else
      class="rounded-md border border-default bg-bg-surface p-4 shadow-xs"
    >
      <MarkdownView
        :source="article?.draft_md ?? ''"
      />
    </div>
  </section>
</template>
