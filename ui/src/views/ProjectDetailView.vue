<script setup lang="ts">
// ProjectDetailView — shared project setup page chrome.
//
// The sidebar owns navigation. This wrapper only gives each project-scoped
// setup route a focused page title, project meta, and status context.

import { computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'

import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import { UiPageShell } from '@/components/ui'
import { useProjectsStore } from '@/stores/projects'

const route = useRoute()
const projects = useProjectsStore()
const { items } = storeToRefs(projects)

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))
const project = computed(() => projects.getById(projectId.value))

const activeKey = computed<string>(() => {
  const name = String(route.name ?? '')
  const match = name.match(/^project-detail-(.+)$/)
  return match ? match[1] : 'overview'
})

type ProjectSetupKey =
  | 'overview'
  | 'voice'
  | 'compliance'
  | 'eeat'
  | 'targets'
  | 'integrations'
  | 'schedules'
  | 'cost-budget'

interface PageCopy {
  title: string
  description: string
}

type ProjectSetupPageCopy = {
  [Key in ProjectSetupKey]: PageCopy
}

const PAGE_COPY = {
  overview: {
    title: 'Overview',
    description: 'Readiness, current work, blockers, and the safest next action.',
  },
  voice: {
    title: 'Voice',
    description: 'Editorial voice profiles used by briefs, drafting, and humanization.',
  },
  compliance: {
    title: 'Compliance',
    description: 'Disclosure rules, jurisdictions, and page placement requirements.',
  },
  eeat: {
    title: 'EEAT',
    description: 'Quality criteria and gates applied before publishing.',
  },
  targets: {
    title: 'Publishing',
    description: 'Destination sites, primary channel selection, and publish configuration.',
  },
  integrations: {
    title: 'Integrations',
    description: 'Vendor credentials and connection readiness for automated procedures.',
  },
  schedules: {
    title: 'Schedules',
    description: 'Recurring project operations and scheduled maintenance.',
  },
  'cost-budget': {
    title: 'Cost & Budget',
    description: 'Monthly spend, vendor caps, alerts, and request-rate controls.',
  },
} satisfies ProjectSetupPageCopy

function isProjectSetupKey(key: string): key is ProjectSetupKey {
  return key in PAGE_COPY
}

const pageCopy = computed(() =>
  isProjectSetupKey(activeKey.value) ? PAGE_COPY[activeKey.value] : PAGE_COPY.overview,
)
const pageBreadcrumbs = computed(() =>
  activeKey.value === 'overview' ? [] : [{ label: pageCopy.value.title }],
)

async function ensureLoaded(): Promise<void> {
  if (project.value) return
  if (items.value.length === 0) await projects.refresh()
}

onMounted(ensureLoaded)
watch(projectId, ensureLoaded)
</script>

<template>
  <UiPageShell>
    <ProjectPageHeader
      :project-id="projectId"
      :title="pageCopy.title"
      :description="pageCopy.description"
      :breadcrumbs="pageBreadcrumbs"
      show-project-status
    />
    <RouterView />
  </UiPageShell>
</template>
