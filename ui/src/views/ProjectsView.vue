<script setup lang="ts">
// ProjectsView — list + create modal.
//
// Opens its create modal automatically when the URL carries `?new=1`
// (driven by ProjectSwitcher's "+ New project" item).

import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  UiBreadcrumbs,
  UiButton,
  UiDialog,
  UiEmptyState,
  UiFormField,
  UiInput,
  UiPageHeader,
  UiPageShell,
} from '@/components/ui'
import { useProjectsStore } from '@/stores/projects'
import { useToastsStore } from '@/stores/toasts'
import type { DataTableColumn } from '@/components/types'
import type { Project } from '@/stores/projects'

const router = useRouter()
const route = useRoute()
const projects = useProjectsStore()
const toasts = useToastsStore()

const { items, loading, nextCursor } = storeToRefs(projects)

const showModal = ref(false)
const submitting = ref(false)

interface NewProject {
  name: string
  slug: string
  domain: string
  niche: string
  locale: string
}

const draft = ref<NewProject>(emptyDraft())

function emptyDraft(): NewProject {
  return { name: '', slug: '', domain: '', niche: '', locale: 'en-US' }
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 80)
}

watch(
  () => draft.value.name,
  (name) => {
    if (!draft.value.slug || draft.value.slug === slugify(draft.value.slug)) {
      draft.value.slug = slugify(name)
    }
  },
)

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
    format: (v) => formatDate(v as string),
  },
]

function formatDate(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString()
  } catch {
    return iso
  }
}

function openModal(): void {
  draft.value = emptyDraft()
  showModal.value = true
}

function closeModal(): void {
  if (submitting.value) return
  showModal.value = false
  if (route.query.new) {
    void router.replace({ path: '/projects' })
  }
}

async function submit(): Promise<void> {
  if (submitting.value) return
  if (!draft.value.name.trim() || !draft.value.domain.trim() || !draft.value.slug.trim()) {
    toasts.error('Missing required fields', 'Name, slug and domain are required.')
    return
  }
  submitting.value = true
  try {
    const created = await projects.create({
      name: draft.value.name.trim(),
      slug: draft.value.slug.trim(),
      domain: draft.value.domain.trim(),
      niche: draft.value.niche.trim() || null,
      locale: draft.value.locale.trim() || 'en-US',
      schedule_json: null,
    })
    toasts.success('Project created', created.name)
    showModal.value = false
    projects.setActiveProjectId(created.id)
    await router.push(`/projects/${created.id}/overview`)
  } catch (err) {
    toasts.error('Failed to create project', err instanceof Error ? err.message : undefined)
  } finally {
    submitting.value = false
  }
}

function openDetail(row: Project): void {
  void router.push(`/projects/${row.id}/overview`)
}

async function loadMore(): Promise<void> {
  await projects.loadMore()
}

const empty = computed<boolean>(() => !loading.value && items.value.length === 0)

onMounted(async () => {
  if (items.value.length === 0) await projects.refresh()
  if (route.query.new === '1') openModal()
})

watch(
  () => route.query.new,
  (next) => {
    if (next === '1') openModal()
  },
)
</script>

<template>
  <UiPageShell>
    <UiPageHeader
      title="Projects"
      description="Create and manage the sites content-stack can research, write, publish, and monitor."
    >
      <template #breadcrumbs>
        <UiBreadcrumbs :items="[{ label: 'Projects' }]" />
      </template>
      <template #actions>
        <UiButton
          variant="primary"
          @click="openModal"
        >
          New project
        </UiButton>
      </template>
    </UiPageHeader>

    <UiEmptyState
      v-if="empty"
      title="No projects yet"
      description="Create your first project to define its slug, domain, locale, and niche."
      size="lg"
    >
      <template #actions>
        <UiButton
          variant="primary"
          @click="openModal"
        >
          Create project
        </UiButton>
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
      @row-click="openDetail"
      @load-more="loadMore"
    >
      <template #cell:is_active="{ row }">
        <StatusBadge
          :status="(row as Project).is_active ? 'active' : 'inactive'"
          kind="project"
        />
      </template>
    </DataTable>

    <UiDialog
      :model-value="showModal"
      title="New project"
      description="Set the base project identity. Publishing and integrations can be configured after creation."
      size="md"
      @update:model-value="(open: boolean) => open ? showModal = true : closeModal()"
    >
      <form
        class="space-y-3"
        @submit.prevent="submit"
      >
        <UiFormField
          v-slot="{ id, describedBy, invalid, required }"
          label="Name"
          required
        >
          <UiInput
            :id="id"
            v-model="draft.name"
            :aria-describedby="describedBy"
            :invalid="invalid"
            :required="required"
            autocomplete="off"
          />
        </UiFormField>

        <UiFormField
          v-slot="{ id, describedBy, invalid, required }"
          label="Slug"
          required
        >
          <UiInput
            :id="id"
            v-model="draft.slug"
            :aria-describedby="describedBy"
            :invalid="invalid"
            :required="required"
            class="[&_.ui-input__field]:font-mono"
            autocomplete="off"
          />
        </UiFormField>

        <UiFormField
          v-slot="{ id, describedBy, invalid, required }"
          label="Domain"
          required
        >
          <UiInput
            :id="id"
            v-model="draft.domain"
            :aria-describedby="describedBy"
            :invalid="invalid"
            :required="required"
            placeholder="example.com"
            autocomplete="off"
          />
        </UiFormField>

        <div class="grid gap-3 sm:grid-cols-2">
          <UiFormField
            v-slot="{ id, describedBy, invalid }"
            label="Niche"
          >
            <UiInput
              :id="id"
              v-model="draft.niche"
              :aria-describedby="describedBy"
              :invalid="invalid"
              autocomplete="off"
            />
          </UiFormField>
          <UiFormField
            v-slot="{ id, describedBy, invalid }"
            label="Locale"
          >
            <UiInput
              :id="id"
              v-model="draft.locale"
              :aria-describedby="describedBy"
              :invalid="invalid"
              placeholder="en-US"
              autocomplete="off"
            />
          </UiFormField>
        </div>
      </form>

      <template #footer>
        <UiButton
          variant="secondary"
          :disabled="submitting"
          @click="closeModal"
        >
          Cancel
        </UiButton>
        <UiButton
          variant="primary"
          :loading="submitting"
          @click="submit"
        >
          Create project
        </UiButton>
      </template>
    </UiDialog>
  </UiPageShell>
</template>
