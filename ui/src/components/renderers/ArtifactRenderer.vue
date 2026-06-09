<script setup lang="ts">
import { computed } from 'vue'

import type { SchemaArtifactOut } from '@/api'
import { UiBadge, UiDescriptionList, UiJsonBlock, UiPanel } from '@/components/ui'
import type { DLItem } from '@/components/ui/UiDescriptionList.vue'
import { formatDateTime, sanitizeForDisplay } from '@/lib/stackos/json'

const props = defineProps<{
  artifact: SchemaArtifactOut
}>()

const metadata = computed(() => sanitizeForDisplay(props.artifact.metadata_json))
const provenance = computed(() => sanitizeForDisplay(props.artifact.provenance_json))
const pluginSlug = computed(() => props.artifact.plugin_slug)

const facts = computed<DLItem[]>(() => [
  { label: 'URI', value: props.artifact.uri, mono: true },
  { label: 'Size', value: props.artifact.size_bytes ?? null },
  {
    label: 'Record',
    value: props.artifact.resource_record_id ? `#${props.artifact.resource_record_id}` : null,
  },
  { label: 'Created', value: formatDateTime(props.artifact.created_at) },
])
</script>

<template>
  <UiPanel :aria-label="`${artifact.kind} artifact`">
    <div class="flex flex-wrap items-start justify-between gap-2">
      <div class="min-w-0">
        <h3
          class="t-h3 truncate text-fg-strong"
          :title="artifact.name || artifact.uri"
        >
          {{ artifact.name || artifact.uri }}
        </h3>
        <p
          v-if="artifact.mime_type"
          class="mt-0.5 font-mono text-2xs text-fg-subtle"
        >
          {{ artifact.mime_type }}
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-1.5">
        <UiBadge
          v-if="pluginSlug"
          tone="accent"
        >
          {{ pluginSlug }}
        </UiBadge>
        <UiBadge>{{ artifact.kind }}</UiBadge>
      </div>
    </div>

    <UiDescriptionList
      class="mt-3"
      layout="grid"
      :columns="4"
      :items="facts"
      aria-label="Artifact facts"
    />

    <div class="mt-3 grid gap-3 lg:grid-cols-2">
      <div class="min-w-0">
        <h4 class="mb-1 text-xs font-medium text-fg-muted">
          Metadata
        </h4>
        <UiJsonBlock
          :data="metadata ?? {}"
          density="compact"
          max-height="14rem"
          wrap
        />
      </div>
      <div class="min-w-0">
        <h4 class="mb-1 text-xs font-medium text-fg-muted">
          Provenance
        </h4>
        <UiJsonBlock
          :data="provenance ?? {}"
          density="compact"
          max-height="14rem"
          wrap
        />
      </div>
    </div>
  </UiPanel>
</template>
