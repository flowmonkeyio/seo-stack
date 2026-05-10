<script setup lang="ts">
// ProjectDetailView — header + TabBar shell.
//
// Each tab is a separate component file under views/project-detail/.
// Tab routing is driven by the URL (last path segment matches `tab.key`)
// so refresh + back/forward both stay on the active tab.

import { computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import ProjectPageHeader from '@/components/domain/ProjectPageHeader.vue'
import TabBar from '@/components/TabBar.vue'
import { UiPageShell } from '@/components/ui'
import { useProjectsStore } from '@/stores/projects'

const route = useRoute()
const router = useRouter()
const projects = useProjectsStore()
const { items } = storeToRefs(projects)

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))
const project = computed(() => projects.getById(projectId.value))

const tabs = [
  { key: 'overview', label: 'Overview' },
  { key: 'voice', label: 'Voice' },
  { key: 'compliance', label: 'Compliance' },
  { key: 'eeat', label: 'EEAT' },
  { key: 'targets', label: 'Targets' },
  { key: 'integrations', label: 'Integrations' },
  { key: 'schedules', label: 'Schedules' },
  { key: 'cost-budget', label: 'Cost & Budget' },
]

const activeKey = computed<string>(() => {
  const name = String(route.name ?? '')
  const match = name.match(/^project-detail-(.+)$/)
  return match ? match[1] : 'overview'
})

function onTabChange(key: string): void {
  void router.push(`/projects/${projectId.value}/${key}`)
}

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
      :title="project?.name"
      description="Project settings, publishing targets, integrations, schedules, and operating controls."
      show-project-status
    >
      <template #tabs>
        <TabBar
          :tabs="tabs"
          :active-key="activeKey"
          aria-label="Project sections"
          @change="onTabChange"
        />
      </template>
    </ProjectPageHeader>
    <div
      :id="`cs-tabpanel-${activeKey}`"
      role="tabpanel"
      :aria-labelledby="`cs-tab-${activeKey}`"
    >
      <RouterView />
    </div>
  </UiPageShell>
</template>
