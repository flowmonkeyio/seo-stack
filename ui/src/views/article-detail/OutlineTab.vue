<script setup lang="ts">
// OutlineTab — read-only outline markdown.

import { computed } from 'vue'

import MarkdownView from '@/components/MarkdownView.vue'
import { useArticlesStore } from '@/stores/articles'

const articlesStore = useArticlesStore()
const article = computed(() => articlesStore.currentDetail)
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-outline-tab-title"
  >
    <div>
      <h2
        id="cs-outline-tab-title"
        class="text-base font-semibold text-fg-strong"
      >
        Outline
      </h2>
      <p class="mt-1 text-sm text-fg-muted">
        The outline is written by the agent and shown here for review.
      </p>
    </div>

    <div
      v-if="!article?.outline_md?.trim()"
      class="rounded-md border border-dashed border-subtle bg-bg-surface px-5 py-8 text-center"
    >
      <h3 class="text-sm font-semibold text-fg-strong">
        No outline yet
      </h3>
      <p class="mt-1 text-sm text-fg-muted">
        The outline artifact will appear here after the agent completes the outline step.
      </p>
    </div>

    <div
      v-else
      class="rounded-md border border-default bg-bg-surface p-4 shadow-xs"
    >
      <MarkdownView
        :source="article?.outline_md ?? ''"
      />
    </div>
  </section>
</template>
