<script setup lang="ts">
// MarkdownView — sanitised markdown render with citation marker support.
//
// Render pipeline:
//   raw markdown
//   → marked() (sync mode, GFM tokenizers on, breaks off)
//   → DOMPurify.sanitize() (strips <script>, on-event handlers, etc.)
//   → citation markers like `[^1]` rewritten to <sup><a href="#cite-1">1</a></sup>
//
// We never execute inline HTML the author didn't already sanitise. We
// turn off `breaks: true` to keep paragraph boundaries predictable.

import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { computed } from 'vue'

interface Props {
  source: string
  /** Show a one-line empty placeholder if `source` is empty/whitespace. */
  emptyMessage?: string
}

const props = withDefaults(defineProps<Props>(), {
  emptyMessage: 'Nothing to display.',
})

marked.setOptions({
  gfm: true,
  breaks: false,
})

const CITATION_RE = /\[\^([\w-]+)\]/g

function rewriteCitations(html: string): string {
  return html.replace(CITATION_RE, (_match, id: string) => {
    const safeId = id.replace(/[^\w-]/g, '')
    return `<sup class="cs-citation"><a href="#cite-${safeId}" data-citation-id="${safeId}">${safeId}</a></sup>`
  })
}

const rendered = computed<string>(() => {
  const trimmed = props.source.trim()
  if (trimmed.length === 0) return ''
  // marked v14 returns string in sync mode by default unless `async: true`.
  const raw = marked.parse(trimmed) as string
  const cited = rewriteCitations(raw)
  return DOMPurify.sanitize(cited, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ['data-citation-id'],
  })
})
</script>

<template>
  <div
    v-if="rendered.length === 0"
    class="text-sm italic text-gray-500 dark:text-gray-400"
  >
    {{ emptyMessage }}
  </div>
  <!-- eslint-disable vue/no-v-html — `rendered` runs through DOMPurify in the script. -->
  <div
    v-else
    class="cs-markdown max-w-none text-sm text-gray-900 dark:text-gray-100"
    v-html="rendered"
  />
</template>

<style scoped>
.cs-markdown :deep(h1) {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 1.25rem 0 0.5rem;
}
.cs-markdown :deep(h2) {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 1rem 0 0.4rem;
}
.cs-markdown :deep(h3) {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0.85rem 0 0.35rem;
}
.cs-markdown :deep(p) {
  margin: 0.5rem 0;
  line-height: 1.5;
}
.cs-markdown :deep(ul),
.cs-markdown :deep(ol) {
  padding-left: 1.5rem;
  margin: 0.5rem 0;
}
.cs-markdown :deep(li) {
  margin: 0.15rem 0;
}
.cs-markdown :deep(code) {
  font-family: ui-monospace, SFMono-Regular, monospace;
  background: rgba(15, 23, 42, 0.06);
  border-radius: 0.25rem;
  padding: 0.05rem 0.3rem;
  font-size: 0.9em;
}
.cs-markdown :deep(pre) {
  background: rgba(15, 23, 42, 0.05);
  border-radius: 0.4rem;
  padding: 0.75rem;
  overflow-x: auto;
  margin: 0.75rem 0;
}
.cs-markdown :deep(pre code) {
  background: transparent;
  padding: 0;
}
.cs-markdown :deep(a) {
  color: #1d4ed8;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.cs-markdown :deep(blockquote) {
  border-left: 3px solid #cbd5e1;
  padding-left: 0.75rem;
  margin: 0.5rem 0;
  color: #475569;
}
.cs-markdown :deep(.cs-citation) {
  margin-left: 0.1rem;
}
</style>
