<script setup lang="ts">
// ProjectsView — project inventory and first-project setup entry.

import { computed, onMounted, reactive, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  UiButton,
  UiCallout,
  UiEmptyState,
  UiFormField,
  UiInput,
  UiPageHeader,
  UiPageShell,
  UiSidePanel,
} from '@/components/ui'
import { formatApiError } from '@/lib/client'
import { useProjectsStore } from '@/stores/projects'
import type { DataTableColumn } from '@/components/types'
import type { Project } from '@/stores/projects'

const router = useRouter()
const projects = useProjectsStore()
const { items, loading, nextCursor, error } = storeToRefs(projects)
const createPanelOpen = ref(false)
const saving = ref(false)
const createError = ref<string | null>(null)
const slugEdited = ref(false)
const form = reactive({
  name: '',
  slug: '',
  domain: '',
  niche: '',
  locale: 'en-US',
})

const columns: DataTableColumn<Project>[] = [
  { key: 'name', label: 'Name', sortable: false },
  { key: 'slug', label: 'Slug', sortable: false, cellClass: 'font-mono text-xs' },
  { key: 'domain', label: 'Domain', sortable: false },
  { key: 'niche', label: 'Niche', sortable: false },
  { key: 'locale', label: 'Locale', sortable: false },
  { key: 'is_active', label: 'Status', sortable: false },
  {
    key: 'updated_at',
    label: 'Updated',
    sortable: false,
    format: (value) => formatDate(value as string),
  },
]

const empty = computed<boolean>(() => !loading.value && items.value.length === 0)

function formatDate(iso: string): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function openDetail(row: Project): void {
  void router.push(`/projects/${row.id}/overview`)
}

function openCreate(): void {
  createError.value = null
  slugEdited.value = false
  createPanelOpen.value = true
}

function normalizeSlug(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function updateSlug(value: string | number | null): void {
  slugEdited.value = true
  form.slug = String(value ?? '')
}

async function saveProject(): Promise<void> {
  createError.value = null
  const slug = normalizeSlug(form.slug || form.name)
  if (!form.name.trim() || !slug || !form.domain.trim()) {
    createError.value = 'Name, slug, and domain are required.'
    return
  }
  saving.value = true
  try {
    const project = await projects.createProject({
      name: form.name.trim(),
      slug,
      domain: form.domain.trim(),
      niche: form.niche.trim() || null,
      locale: form.locale.trim() || 'en-US',
      schedule_json: null,
    })
    createPanelOpen.value = false
    form.name = ''
    form.slug = ''
    form.domain = ''
    form.niche = ''
    form.locale = 'en-US'
    slugEdited.value = false
    await router.push(`/projects/${project.id}/setup`)
  } catch (err) {
    createError.value = formatApiError(err, 'failed to create project')
  } finally {
    saving.value = false
  }
}

async function loadMore(): Promise<void> {
  await projects.loadMore()
}

onMounted(async () => {
  if (items.value.length === 0) await projects.refresh()
})

watch(
  () => form.name,
  (name) => {
    if (!slugEdited.value) form.slug = normalizeSlug(name)
  },
)
</script>

<template>
  <UiPageShell>
    <UiPageHeader
      title="Projects"
      description="Configured workspaces for plugins, runs, resources, and project memory."
    >
      <template #actions>
        <UiButton @click="openCreate"> New project </UiButton>
      </template>
    </UiPageHeader>

    <UiCallout v-if="error" tone="danger">
      {{ error }}
    </UiCallout>

    <UiEmptyState
      v-if="empty"
      title="No projects yet"
      description="Create a project to enable plugins, connections, templates, and runs."
      size="lg"
    >
      <template #actions>
        <UiButton @click="openCreate"> New project </UiButton>
      </template>
    </UiEmptyState>

    <DataTable
      v-else
      :items="items"
      :columns="columns"
      :loading="loading"
      :next-cursor="nextCursor"
      aria-label="Projects"
      empty-message="No projects yet"
      interactive
      @row-click="openDetail"
      @load-more="loadMore"
    >
      <template #cell:is_active="{ row }">
        <StatusBadge :status="(row as Project).is_active ? 'active' : 'inactive'" kind="project" />
      </template>
    </DataTable>

    <UiSidePanel v-model="createPanelOpen" title="New Project" size="md">
      <div class="space-y-4">
        <UiCallout v-if="createError" tone="danger">
          {{ createError }}
        </UiCallout>

        <UiFormField label="Name">
          <UiInput v-model="form.name" placeholder="Acme" />
        </UiFormField>

        <UiFormField label="Slug">
          <UiInput
            :model-value="form.slug"
            placeholder="acme"
            @update:model-value="updateSlug"
            @blur="form.slug = normalizeSlug(form.slug)"
          />
        </UiFormField>

        <UiFormField label="Domain">
          <UiInput v-model="form.domain" placeholder="example.com" />
        </UiFormField>

        <UiFormField label="Niche">
          <UiInput v-model="form.niche" placeholder="Optional" />
        </UiFormField>

        <UiFormField label="Locale">
          <UiInput v-model="form.locale" placeholder="en-US" />
        </UiFormField>
      </div>

      <template #footer>
        <UiButton variant="secondary" @click="createPanelOpen = false"> Cancel </UiButton>
        <UiButton :disabled="saving" @click="saveProject"> Create </UiButton>
      </template>
    </UiSidePanel>
  </UiPageShell>
</template>
