<script setup lang="ts">
// ProjectSwitcher — combobox showing the active project + dropdown to swap.
//
// Behavior:
//   - Displays the active project name + chevron in collapsed state
//   - Click to open dropdown with list of all projects (active first)
//   - "+ New project" item at the bottom navigates to /projects (where
//     the New Project modal lives — single source of truth for create)
//   - Selecting a project calls `projectsStore.activate(id)` and
//     navigates to `/projects/{id}/overview`

import { computed, ref, onBeforeUnmount, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'

import { useProjectsStore } from '@/stores/projects'
import { useToastsStore } from '@/stores/toasts'

const projects = useProjectsStore()
const toasts = useToastsStore()
const router = useRouter()
const { items, activeProject } = storeToRefs(projects)

const open = ref(false)
const rootEl = ref<HTMLDivElement | null>(null)

function toggle(): void {
  open.value = !open.value
}
function close(): void {
  open.value = false
}

const sortedItems = computed(() => {
  const live = [...items.value].filter((p) => p.is_active)
  const archived = [...items.value].filter((p) => !p.is_active)
  return [...live, ...archived]
})

async function pick(id: number): Promise<void> {
  close()
  if (activeProject.value?.id === id) {
    await router.push(`/projects/${id}/overview`)
    return
  }
  try {
    await projects.activate(id)
    toasts.success('Project switched')
    await router.push(`/projects/${id}/overview`)
  } catch (err) {
    toasts.error('Failed to switch project', err instanceof Error ? err.message : undefined)
  }
}

function newProject(): void {
  close()
  void router.push({ path: '/projects', query: { new: '1' } })
}

function onClickOutside(e: MouseEvent): void {
  if (!rootEl.value) return
  if (!rootEl.value.contains(e.target as Node)) close()
}

onMounted(() => document.addEventListener('mousedown', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('mousedown', onClickOutside))
</script>

<template>
  <div
    ref="rootEl"
    class="relative"
  >
    <button
      type="button"
      class="flex w-full items-center justify-between gap-2 rounded-sm border border-default bg-bg-surface px-3 py-2 text-sm shadow-xs hover:bg-bg-surface-alt focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      :aria-expanded="open"
      aria-haspopup="listbox"
      @click="toggle"
    >
      <span class="truncate text-left">
        <span
          v-if="activeProject"
          class="font-medium text-fg-strong"
        >
          {{ activeProject.name }}
        </span>
        <span
          v-else
          class="text-fg-muted"
        >No project selected</span>
      </span>
      <span
        aria-hidden="true"
        class="text-xs text-fg-muted"
      >▾</span>
    </button>
    <div
      v-if="open"
      role="listbox"
      class="absolute z-dropdown mt-1 max-h-72 w-full overflow-y-auto rounded-md border border-default bg-bg-surface py-1 shadow-md"
    >
      <button
        v-for="p in sortedItems"
        :key="p.id"
        role="option"
        :aria-selected="p.id === activeProject?.id"
        type="button"
        class="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-bg-surface-alt focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
        :class="p.id === activeProject?.id ? 'bg-accent-subtle' : ''"
        @click="pick(p.id)"
      >
        <span>
          <span class="block truncate font-medium text-fg-strong">
            {{ p.name }}
          </span>
          <span class="block truncate text-xs text-fg-muted">
            {{ p.slug }} · {{ p.domain }}
          </span>
        </span>
        <span
          v-if="!p.is_active"
          class="rounded-xs bg-neutral-subtle px-1.5 py-0.5 text-[10px] font-medium text-neutral-fg"
        >
          archived
        </span>
      </button>
      <div
        v-if="sortedItems.length === 0"
        class="px-3 py-2 text-sm text-fg-muted"
      >
        No projects yet.
      </div>
      <button
        type="button"
        class="mt-1 block w-full border-t border-subtle px-3 py-2 text-left text-sm font-medium text-fg-link hover:bg-accent-subtle"
        @click="newProject"
      >
        + New project
      </button>
    </div>
  </div>
</template>
