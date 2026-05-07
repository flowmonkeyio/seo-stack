<script setup lang="ts">
// ProjectDetailView — header + TabBar shell.
//
// Each tab is a separate component file under views/project-detail/.
// Tab routing is driven by the URL (last path segment matches `tab.key`)
// so refresh + back/forward both stay on the active tab.

import { computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import StatusBadge from '@/components/StatusBadge.vue'
import TabBar from '@/components/TabBar.vue'
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
  <div class="mx-auto max-w-6xl">
    <header class="mb-4">
      <div class="flex flex-wrap items-baseline gap-3">
        <h1 class="text-2xl font-bold tracking-tight">
          {{ project?.name ?? 'Project' }}
        </h1>
        <StatusBadge
          v-if="project"
          :status="project.is_active ? 'active' : 'inactive'"
          kind="project"
        />
      </div>
      <p
        v-if="project"
        class="mt-1 text-sm text-gray-600 dark:text-gray-400"
      >
        <span class="font-mono">{{ project.slug }}</span> · {{ project.domain }} ·
        {{ project.locale }}
      </p>
    </header>
    <TabBar
      :tabs="tabs"
      :active-key="activeKey"
      aria-label="Project sections"
      @change="onTabChange"
    />
    <div
      :id="`cs-tabpanel-${activeKey}`"
      role="tabpanel"
      :aria-labelledby="`cs-tab-${activeKey}`"
      class="mt-4"
    >
      <RouterView />
    </div>
  </div>
</template>
