<script setup lang="ts">
// EditedTab — read-only edited markdown.

import { computed } from 'vue'

import MarkdownView from '@/components/MarkdownView.vue'
import { useArticlesStore } from '@/stores/articles'

const articlesStore = useArticlesStore()
const article = computed(() => articlesStore.currentDetail)
</script>

<template>
  <section
    class="space-y-4"
    aria-labelledby="cs-edited-tab-title"
  >
    <div>
      <h2
        id="cs-edited-tab-title"
        class="text-base font-semibold text-fg-strong"
      >
        Edited body
      </h2>
      <p class="mt-1 text-sm text-fg-muted">
        Final editing and humanizing are agent-owned. This view shows the artifact scored by EEAT
        and used by publish skills.
      </p>
    </div>

    <div
      v-if="!article?.edited_md?.trim()"
      class="rounded-md border border-dashed border-subtle bg-bg-surface px-5 py-8 text-center"
    >
      <h3 class="text-sm font-semibold text-fg-strong">
        No edited body yet
      </h3>
      <p class="mt-1 text-sm text-fg-muted">
        The edited artifact will appear here after the agent completes editing and humanizing.
      </p>
    </div>

    <div
      v-else
      class="rounded-md border border-default bg-bg-surface p-4 shadow-xs"
    >
      <MarkdownView
        :source="article?.edited_md ?? ''"
      />
    </div>
  </section>
</template>
