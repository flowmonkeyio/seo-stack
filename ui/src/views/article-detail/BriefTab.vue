<script setup lang="ts">
// BriefTab — render `articles.brief_json` as an operator-readable editorial brief.

import { computed } from 'vue'

import KvList from '@/components/KvList.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import { UiAdvancedJsonPanel } from '@/components/ui'
import { useArticlesStore } from '@/stores/articles'

defineProps<{
  articleId: number
}>()

const articlesStore = useArticlesStore()

type BriefJsonValue = string | number | boolean | null | BriefJsonValue[] | BriefJsonObject

interface BriefJsonObject {
  [key: string]: BriefJsonValue
}

const article = computed(() => articlesStore.currentDetail)
const briefJson = computed<BriefJsonObject>(() => {
  const j = article.value?.brief_json
  if (isBriefJsonObject(j)) return j
  return {}
})

const items = computed(() => {
  const j = briefJson.value
  return Object.keys(j)
    .sort((a, b) => sortKey(a) - sortKey(b))
    .map((k) => ({ key: k, label: labelFor(k), value: j[k] }))
})

const BRIEF_ORDER = [
  'title',
  'thesis',
  'audience',
  'intent',
  'primary_kw',
  'secondary_kws',
  'target_word_count',
  'depth',
  'research_summary',
  'source_quality_summary',
  'outline_hint_md',
  'schema_types',
  'schema_skipped',
  'eeat_plan',
  'image_directives',
  'compliance_jurisdictions',
]

function sortKey(key: string): number {
  const idx = BRIEF_ORDER.indexOf(key)
  return idx >= 0 ? idx : BRIEF_ORDER.length + key.localeCompare('zzzz')
}

function labelFor(key: string): string {
  switch (key) {
    case 'title':
      return 'Title'
    case 'thesis':
      return 'Thesis'
    case 'audience':
      return 'Audience'
    case 'intent':
      return 'Search intent'
    case 'primary_kw':
      return 'Primary keyword'
    case 'secondary_kws':
      return 'Secondary keywords'
    case 'target_word_count':
      return 'Target word count'
    case 'voice_id':
      return 'Voice profile'
    case 'depth':
      return 'Editorial depth'
    case 'research_summary':
      return 'Research summary'
    case 'source_quality_summary':
      return 'Source quality'
    case 'outline_hint_md':
      return 'Outline guidance'
    case 'schema_types':
      return 'Schema types'
    case 'schema_skipped':
      return 'Schema notes'
    case 'eeat_plan':
      return 'EEAT plan'
    case 'image_directives':
      return 'Image direction'
    case 'compliance_jurisdictions':
      return 'Compliance jurisdictions'
    case 'simulation':
      return 'Simulation mode'
    default:
      return key
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase())
  }
}

function isBriefJsonObject(value: unknown): value is BriefJsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isObjectArray(value: unknown): value is BriefJsonObject[] {
  return Array.isArray(value) && value.length > 0 && value.every(isBriefJsonObject)
}

function valueSummary(value: unknown): string {
  if (!isBriefJsonObject(value)) return String(value)
  const preferred = ['title', 'name', 'url', 'kind', 'type', 'label']
  for (const key of preferred) {
    const found = value[key]
    if (typeof found === 'string' && found.trim()) return found
  }
  return `${Object.keys(value).length} fields`
}
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
    </div>

    <div>
      <p
        v-if="items.length === 0"
        class="rounded-md border border-dashed border-default bg-bg-surface p-4 text-sm text-fg-muted"
      >
        Brief not yet written.
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
            class="text-fg-muted"
          >—</span>
          <div
            v-else-if="isObjectArray(value)"
            class="space-y-2"
          >
            <UiAdvancedJsonPanel
              v-for="(entry, idx) in value"
              :key="idx"
              :title="`${labelFor(key)} ${idx + 1}`"
              :summary="valueSummary(entry)"
              :data="entry"
            />
          </div>
          <span
            v-else-if="Array.isArray(value)"
            class="font-mono text-xs"
          >
            {{ (value as unknown[]).map((v) => valueSummary(v)).join(', ') }}
          </span>
          <div
            v-else-if="typeof value === 'string' && (key.endsWith('_md') || key === 'research_summary' || key === 'outline_hint_md')"
            class="cs-brief-markdown"
          >
            <MarkdownView :source="value as string" />
          </div>
          <span v-else-if="typeof value === 'string'">{{ value }}</span>
          <span v-else-if="typeof value === 'number' || typeof value === 'boolean'">{{ String(value) }}</span>
          <UiAdvancedJsonPanel
            v-else-if="isBriefJsonObject(value)"
            :title="labelFor(key)"
            :summary="valueSummary(value)"
            :data="value"
          />
          <pre
            v-else
            class="overflow-x-auto rounded-sm bg-bg-surface p-2 font-mono text-xs text-fg-default"
          >{{ JSON.stringify(value, null, 2) }}</pre>
        </template>
      </KvList>
    </div>
  </section>
</template>

<style scoped>
.cs-brief-markdown :deep(h1) {
  font-size: 1.15rem;
  line-height: 1.4;
  margin: 0.25rem 0 0.35rem;
}

.cs-brief-markdown :deep(h2) {
  font-size: 1rem;
  line-height: 1.4;
  margin: 0.6rem 0 0.25rem;
}

.cs-brief-markdown :deep(h3),
.cs-brief-markdown :deep(p) {
  margin-top: 0.35rem;
  margin-bottom: 0.35rem;
}
</style>
