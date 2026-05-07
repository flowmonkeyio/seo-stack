<script setup lang="ts">
// App shell — sidebar + main content + toast region.
//
// Sidebar holds the brand, ProjectSwitcher, primary nav, and theme toggle.
// At < md the layout collapses to a single column with a top-of-page nav.

import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import ProjectSwitcher from '@/components/ProjectSwitcher.vue'
import { useAuthStore } from '@/stores/auth'
import { useProjectsStore } from '@/stores/projects'
import { useToastsStore } from '@/stores/toasts'

const auth = useAuthStore()
const projects = useProjectsStore()
const toasts = useToastsStore()
const route = useRoute()

const { activeProject } = storeToRefs(projects)
const { items: toastItems } = storeToRefs(toasts)

const theme = ref<'light' | 'dark'>('light')
const drawerOpen = ref(false)

function applyTheme(): void {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', theme.value === 'dark')
}

function toggleTheme(): void {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  applyTheme()
  try {
    localStorage.setItem('cs:theme', theme.value)
  } catch {
    /* localStorage may be disabled — that's fine. */
  }
}

onMounted(() => {
  try {
    const stored = localStorage.getItem('cs:theme')
    if (stored === 'dark' || stored === 'light') theme.value = stored
  } catch {
    /* ignore */
  }
  applyTheme()
})

interface NavItem {
  label: string
  to: string
  milestone?: string
}

const projectNav = computed<NavItem[]>(() => {
  const id = activeProject.value?.id
  if (!id) return []
  return [
    { label: 'Overview', to: `/projects/${id}/overview` },
    { label: 'Clusters', to: `/projects/${id}/clusters` },
    { label: 'Topics', to: `/projects/${id}/topics` },
    { label: 'Articles', to: `/projects/${id}/articles` },
    { label: 'Interlinks', to: `/projects/${id}/interlinks` },
    { label: 'GSC', to: `/projects/${id}/gsc` },
    { label: 'Drift', to: `/projects/${id}/drift` },
    { label: 'Runs', to: `/projects/${id}/runs` },
    { label: 'Procedures', to: `/projects/${id}/procedures` },
  ]
})

function closeDrawer(): void {
  drawerOpen.value = false
}

function dismissToast(id: number): void {
  toasts.dismiss(id)
}

const isAuthErrorRoute = computed(() => route.name === 'auth-error')
</script>

<template>
  <div class="flex min-h-screen flex-col md:flex-row">
    <button
      type="button"
      class="m-2 inline-flex items-center justify-center rounded border border-gray-300 px-3 py-1.5 text-sm md:hidden dark:border-gray-700"
      :aria-expanded="drawerOpen"
      aria-controls="cs-sidebar"
      @click="drawerOpen = !drawerOpen"
    >
      Menu
    </button>

    <aside
      id="cs-sidebar"
      class="border-b border-gray-200 bg-white md:w-60 md:flex-shrink-0 md:border-b-0 md:border-r dark:border-gray-800 dark:bg-gray-900"
      :class="drawerOpen ? 'block' : 'hidden md:block'"
      aria-label="Primary navigation"
    >
      <div class="flex items-center gap-2 px-4 py-4 md:px-6">
        <span
          class="inline-flex h-8 w-8 items-center justify-center rounded bg-gray-900 font-mono text-sm font-bold text-white dark:bg-gray-100 dark:text-gray-900"
          aria-hidden="true"
        >cs</span>
        <div>
          <div class="text-sm font-semibold leading-tight">
            content-stack
          </div>
          <div class="text-xs text-gray-500 dark:text-gray-400">
            M5 build
          </div>
        </div>
      </div>

      <div class="px-3 pb-3 md:px-4">
        <ProjectSwitcher />
      </div>

      <nav class="px-2 pb-4 md:px-4">
        <ul class="space-y-1 text-sm">
          <li>
            <RouterLink
              to="/projects"
              class="block rounded px-3 py-2 text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800"
              active-class="bg-gray-100 font-medium text-gray-900 dark:bg-gray-800 dark:text-white"
              @click="closeDrawer"
            >
              All projects
            </RouterLink>
          </li>
        </ul>

        <p
          v-if="projectNav.length === 0"
          class="mt-4 px-3 text-xs text-gray-500 dark:text-gray-400"
        >
          Pick a project to see the navigation.
        </p>
        <ul
          v-else
          class="mt-4 space-y-1 text-sm"
        >
          <li
            v-for="item in projectNav"
            :key="item.to"
          >
            <RouterLink
              :to="item.to"
              class="flex items-center justify-between rounded px-3 py-2 text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800"
              active-class="bg-gray-100 font-medium text-gray-900 dark:bg-gray-800 dark:text-white"
              @click="closeDrawer"
            >
              <span>{{ item.label }}</span>
              <span
                v-if="item.milestone"
                class="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
              >
                {{ item.milestone }}
              </span>
            </RouterLink>
          </li>
        </ul>
      </nav>

      <div class="border-t border-gray-100 px-4 py-3 dark:border-gray-800">
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded border border-gray-300 px-3 py-1.5 text-xs hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:border-gray-700 dark:hover:bg-gray-800"
          :aria-pressed="theme === 'dark'"
          @click="toggleTheme"
        >
          <span aria-hidden="true">{{ theme === 'dark' ? '☾' : '☀' }}</span>
          <span>{{ theme === 'dark' ? 'Dark' : 'Light' }} theme</span>
        </button>
      </div>
    </aside>

    <main class="relative flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
      <ul
        v-if="toastItems.length > 0"
        class="pointer-events-none fixed inset-x-4 top-3 z-50 mx-auto flex max-w-md flex-col gap-2 sm:left-auto sm:right-4 sm:mx-0"
        aria-live="polite"
      >
        <li
          v-for="t in toastItems"
          :key="t.id"
          role="status"
          class="pointer-events-auto rounded border p-3 text-sm shadow"
          :class="
            t.kind === 'error'
              ? 'border-red-300 bg-red-50 text-red-900 dark:border-red-700 dark:bg-red-900/40 dark:text-red-100'
              : t.kind === 'success'
                ? 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-100'
                : 'border-gray-300 bg-gray-50 text-gray-900 dark:border-gray-700 dark:bg-gray-900/60 dark:text-gray-100'
          "
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="font-medium">
                {{ t.title }}
              </div>
              <div
                v-if="t.detail"
                class="mt-1 text-xs opacity-90"
              >
                {{ t.detail }}
              </div>
            </div>
            <button
              type="button"
              class="rounded p-1 text-xs opacity-70 hover:opacity-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-current"
              :aria-label="`Dismiss ${t.title}`"
              @click="dismissToast(t.id)"
            >
              ×
            </button>
          </div>
        </li>
      </ul>

      <div
        v-if="!auth.ready && !isAuthErrorRoute"
        class="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-900/40 dark:text-amber-100"
        role="alert"
      >
        Authenticating with the daemon…
      </div>

      <RouterView />
    </main>
  </div>
</template>
