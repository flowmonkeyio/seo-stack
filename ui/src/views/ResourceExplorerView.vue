<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import ArtifactRenderer from '@/components/renderers/ArtifactRenderer.vue'
import ResourceViewRenderer from '@/components/renderers/ResourceViewRenderer.vue'
import {
  UiBadge,
  UiCallout,
  UiFormField,
  UiJsonBlock,
  UiPageShell,
  UiPanel,
  UiSectionHeader,
  UiSelect,
} from '@/components/ui'
import type { DataTableColumn } from '@/components/types'
import type { SchemaResourceOut, SchemaResourceRecordOut } from '@/api'
import { formatDateTime, sanitizeForDisplay } from '@/lib/stackos/json'
import { useStackOsCatalogStore } from '@/stores/plugins'
import { useStackOsResourcesStore } from '@/stores/stackosResources'

const route = useRoute()
const catalogStore = useStackOsCatalogStore()
const resourcesStore = useStackOsResourcesStore()
const { enabledPlugins } = storeToRefs(catalogStore)
const { resources, records, artifacts, loading, error } = storeToRefs(resourcesStore)

const projectId = computed(() => Number.parseInt(route.params.id as string, 10))
const pluginSlug = ref(String(route.query.plugin_slug ?? ''))
const resourceKey = ref(String(route.query.resource_key ?? ''))
const selectedResource = ref<SchemaResourceOut | null>(null)
const selectedRecord = ref<SchemaResourceRecordOut | null>(null)

const selectedPlugin = computed(
  () => enabledPlugins.value.find((plugin) => plugin.slug === pluginSlug.value) ?? null,
)
const pageTitle = computed(() =>
  selectedPlugin.value ? `${selectedPlugin.value.name} Data` : 'Data Explorer',
)
const pageDescription = computed(() =>
  selectedPlugin.value
    ? `Schemas, records, and artifacts owned by ${selectedPlugin.value.name}.`
    : 'Plugin data schemas, project records, and artifact references.',
)
const breadcrumbLabel = computed(() => (selectedPlugin.value ? 'Data' : 'Data Explorer'))
const selectedSchemaJson = computed(() =>
  selectedResource.value ? sanitizeForDisplay(selectedResource.value.schema_json ?? null) : null,
)
const selectedUiSchemaJson = computed(() =>
  selectedResource.value ? sanitizeForDisplay(selectedResource.value.ui_schema_json ?? null) : null,
)
const selectedConfigJson = computed(() =>
  selectedResource.value ? sanitizeForDisplay(selectedResource.value.config_json ?? null) : null,
)

const pluginOptions = computed(() => [
  { value: '', label: 'All plugins' },
  ...enabledPlugins.value.map((plugin) => ({ value: plugin.slug, label: plugin.name })),
])

const resourceOptions = computed(() => [
  { value: '', label: 'All schemas' },
  ...resources.value.map((resource) => ({ value: resource.key, label: resource.name })),
])

const resourceColumns: DataTableColumn<SchemaResourceOut>[] = [
  { key: 'plugin_slug', label: 'Plugin' },
  { key: 'key', label: 'Key' },
  { key: 'name', label: 'Name' },
  { key: 'description', label: 'Description' },
]

const recordColumns: DataTableColumn<SchemaResourceRecordOut>[] = [
  { key: 'plugin_slug', label: 'Plugin' },
  { key: 'resource_key', label: 'Resource' },
  { key: 'title', label: 'Title', format: (value) => String(value ?? '-') },
  { key: 'updated_at', label: 'Updated', format: (value) => formatDateTime(String(value)) },
]

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  await Promise.all([
    catalogStore.refresh(projectId.value),
    resourcesStore.refresh(projectId.value, {
      pluginSlug: pluginSlug.value || null,
      resourceKey: resourceKey.value || null,
    }),
  ])
  selectedResource.value =
    resources.value.find((resource) => resource.key === resourceKey.value) ?? resources.value[0] ?? null
  selectedRecord.value = records.value[0] ?? null
}

function onPlugin(value: string | number | null): void {
  pluginSlug.value = String(value ?? '')
  resourceKey.value = ''
  void load()
}

function onResource(value: string | number | null): void {
  resourceKey.value = String(value ?? '')
  void load()
}

onMounted(load)
watch(projectId, load)
watch(records, (items) => {
  if (!selectedRecord.value || !items.some((record) => record.id === selectedRecord.value?.id)) {
    selectedRecord.value = items[0] ?? null
  }
})
watch(resources, (items) => {
  if (!selectedResource.value || !items.some((resource) => resource.id === selectedResource.value?.id)) {
    selectedResource.value =
      items.find((resource) => resource.key === resourceKey.value) ?? items[0] ?? null
  }
})
watch(
  () => route.query,
  () => {
    pluginSlug.value = String(route.query.plugin_slug ?? '')
    resourceKey.value = String(route.query.resource_key ?? '')
    void load()
  },
)
</script>

<template>
  <UiPageShell>
    <ProjectPageHeader
      :project-id="projectId"
      :title="pageTitle"
      :description="pageDescription"
      :breadcrumbs="[{ label: breadcrumbLabel }]"
    />

    <UiCallout
      v-if="error"
      tone="danger"
    >
      {{ error }}
    </UiCallout>

    <UiPanel class="p-4">
      <div class="grid gap-3 md:grid-cols-2 lg:grid-cols-[260px_260px_1fr]">
        <UiFormField label="Plugin">
          <UiSelect
            :model-value="pluginSlug"
            :options="pluginOptions"
            @update:model-value="onPlugin"
          />
        </UiFormField>
        <UiFormField label="Schema">
          <UiSelect
            :model-value="resourceKey"
            :options="resourceOptions"
            @update:model-value="onResource"
          />
        </UiFormField>
        <div class="flex items-end gap-2">
          <UiBadge>{{ resources.length }} schemas</UiBadge>
          <UiBadge>{{ records.length }} records</UiBadge>
          <UiBadge>{{ artifacts.length }} artifacts</UiBadge>
        </div>
      </div>
    </UiPanel>

    <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(26rem,38rem)] xl:items-start">
      <div class="space-y-4">
        <UiPanel class="p-4">
          <UiSectionHeader
            title="Schemas"
            as="h3"
          >
            <template #actions>
              <UiBadge>{{ resources.length }}</UiBadge>
            </template>
          </UiSectionHeader>
          <DataTable
            :items="resources"
            :columns="resourceColumns"
            :loading="loading"
            :selected-id="selectedResource?.id"
            max-height="18rem"
            aria-label="Resource schemas"
            empty-message="No resource schemas."
            interactive
            @row-click="(row) => (selectedResource = row)"
          >
            <template #cell:plugin_slug="{ value }">
              <UiBadge tone="accent">{{ value }}</UiBadge>
            </template>
          </DataTable>
        </UiPanel>

        <UiPanel class="p-4">
          <UiSectionHeader
            title="Records"
            as="h3"
          >
            <template #actions>
              <UiBadge>{{ records.length }}</UiBadge>
            </template>
          </UiSectionHeader>
          <DataTable
            :items="records"
            :columns="recordColumns"
            :loading="loading"
            :selected-id="selectedRecord?.id"
            max-height="calc(100vh - 31rem)"
            aria-label="Resource records"
            empty-message="No resource records."
            interactive
            @row-click="(row) => (selectedRecord = row)"
          >
            <template #cell:plugin_slug="{ value }">
              <UiBadge tone="accent">{{ value }}</UiBadge>
            </template>
          </DataTable>
        </UiPanel>
    </div>

      <div class="space-y-4 xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:overflow-y-auto">
        <UiPanel
          v-if="selectedResource"
          class="p-4"
        >
          <UiSectionHeader
            title="Schema Details"
            :description="selectedResource.description"
          >
            <template #actions>
              <UiBadge tone="accent">{{ selectedResource.plugin_slug }}</UiBadge>
              <UiBadge>{{ selectedResource.key }}</UiBadge>
            </template>
          </UiSectionHeader>

          <dl class="mt-4 grid gap-3 text-sm md:grid-cols-2">
            <div class="min-w-0">
              <dt class="text-xs text-fg-muted">Name</dt>
              <dd class="truncate font-medium text-fg-strong">{{ selectedResource.name }}</dd>
            </div>
            <div class="min-w-0">
              <dt class="text-xs text-fg-muted">Key</dt>
              <dd class="truncate font-mono">{{ selectedResource.key }}</dd>
            </div>
          </dl>

          <details class="mt-4 rounded-md border border-subtle bg-bg-surface">
            <summary class="cursor-pointer px-3 py-2 text-sm font-medium text-fg-default focus-ring">
              Schema JSON
            </summary>
            <div class="border-t border-subtle p-3">
              <UiJsonBlock
                :data="selectedSchemaJson"
                density="compact"
                max-height="16rem"
                wrap
              />
            </div>
          </details>

          <details class="mt-3 rounded-md border border-subtle bg-bg-surface">
            <summary class="cursor-pointer px-3 py-2 text-sm font-medium text-fg-default focus-ring">
              UI Schema JSON
            </summary>
            <div class="border-t border-subtle p-3">
              <UiJsonBlock
                :data="selectedUiSchemaJson"
                density="compact"
                max-height="14rem"
                wrap
              />
            </div>
          </details>

          <details class="mt-3 rounded-md border border-subtle bg-bg-surface">
            <summary class="cursor-pointer px-3 py-2 text-sm font-medium text-fg-default focus-ring">
              Config JSON
            </summary>
            <div class="border-t border-subtle p-3">
              <UiJsonBlock
                :data="selectedConfigJson"
                density="compact"
                max-height="14rem"
                wrap
              />
            </div>
          </details>
        </UiPanel>

        <section v-if="selectedRecord" class="space-y-3">
          <UiSectionHeader
            title="Record Details"
            :description="`Selected ${selectedRecord.resource_key} #${selectedRecord.id}`"
          >
            <template #actions>
              <UiBadge tone="accent">{{ selectedRecord.plugin_slug }}</UiBadge>
              <UiBadge>{{ selectedRecord.resource_key }}</UiBadge>
            </template>
          </UiSectionHeader>
          <ResourceViewRenderer :record="selectedRecord" />
        </section>

        <section v-if="artifacts.length > 0" class="space-y-3">
          <UiSectionHeader title="Artifacts">
            <template #actions>
              <UiBadge>{{ artifacts.length }}</UiBadge>
            </template>
          </UiSectionHeader>
          <div class="grid gap-3">
            <ArtifactRenderer
              v-for="artifact in artifacts"
              :key="artifact.id"
              :artifact="artifact"
            />
          </div>
        </section>
      </div>
    </div>
  </UiPageShell>
</template>
