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
  document.documentElement.dataset.theme = theme.value
  document.documentElement.style.colorScheme = theme.value
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
  description?: string
  matchPrefix?: boolean
}

interface NavSection {
  label: string
  items: NavItem[]
}

const projectNavSections = computed<NavSection[]>(() => {
  const id = activeProject.value?.id
  if (!id) return []
  return [
    {
      label: 'Command',
      items: [
        { label: 'Overview', to: `/projects/${id}/overview`, description: 'Readiness and next action' },
      ],
    },
    {
      label: 'Content pipeline',
      items: [
        { label: 'Clusters', to: `/projects/${id}/clusters`, description: 'Topical structure' },
        { label: 'Topics', to: `/projects/${id}/topics`, description: 'Queue and approvals' },
        { label: 'Articles', to: `/projects/${id}/articles`, description: 'Production workspace', matchPrefix: true },
        { label: 'Procedures', to: `/projects/${id}/procedures`, description: 'Guided operations' },
      ],
    },
    {
      label: 'Project setup',
      items: [
        { label: 'Voice', to: `/projects/${id}/voice`, description: 'Editorial profile' },
        { label: 'Compliance', to: `/projects/${id}/compliance`, description: 'Rules and disclosures' },
        { label: 'EEAT', to: `/projects/${id}/eeat`, description: 'Quality criteria' },
        { label: 'Publishing', to: `/projects/${id}/targets`, description: 'Targets and channels' },
        { label: 'Integrations', to: `/projects/${id}/integrations`, description: 'Vendor credentials' },
        { label: 'Schedules', to: `/projects/${id}/schedules`, description: 'Recurring work' },
        { label: 'Cost & Budget', to: `/projects/${id}/cost-budget`, description: 'Spend controls' },
      ],
    },
    {
      label: 'Monitoring',
      items: [
        { label: 'Interlinks', to: `/projects/${id}/interlinks`, description: 'Internal link queue' },
        { label: 'Search Console', to: `/projects/${id}/gsc`, description: 'Queries and redirects' },
        { label: 'Drift', to: `/projects/${id}/drift`, description: 'Content baselines' },
        { label: 'Runs', to: `/projects/${id}/runs`, description: 'Execution audit', matchPrefix: true },
      ],
    },
  ]
})

function navItemClass(item: NavItem): string {
  const active = item.matchPrefix
    ? route.path === item.to || route.path.startsWith(`${item.to}/`)
    : route.path === item.to
  return [
    'relative block rounded-md px-3 py-1.5 text-sm transition-colors duration-fast focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus',
    active
      ? 'bg-accent-subtle text-accent-fg shadow-xs before:absolute before:bottom-1.5 before:left-1 before:top-1.5 before:w-0.5 before:rounded-full before:bg-accent'
      : 'text-fg-default hover:bg-bg-surface-alt',
  ].join(' ')
}

function closeDrawer(): void {
  drawerOpen.value = false
}

function dismissToast(id: number): void {
  toasts.dismiss(id)
}

const isAuthErrorRoute = computed(() => route.name === 'auth-error')
</script>

<template>
  <div class="flex min-h-screen flex-col bg-bg-app text-fg-default md:flex-row">
    <button
      type="button"
      class="m-3 inline-flex items-center justify-center rounded-md border border-default bg-bg-surface px-3 py-2 text-sm font-medium text-fg-default shadow-xs hover:bg-bg-surface-alt focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus md:hidden"
      :aria-expanded="drawerOpen"
      aria-controls="cs-sidebar"
      @click="drawerOpen = !drawerOpen"
    >
      Menu
    </button>

    <aside
      id="cs-sidebar"
      class="border-b border-default bg-bg-surface md:sticky md:top-0 md:h-screen md:w-64 md:flex-shrink-0 md:border-b-0 md:border-r"
      :class="drawerOpen ? 'block' : 'hidden md:block'"
      aria-label="Primary navigation"
    >
      <div class="flex h-full flex-col">
        <div class="border-b border-subtle px-4 py-4">
          <div class="flex items-center gap-3">
            <span
              class="inline-flex h-9 w-9 items-center justify-center rounded-md bg-bg-inverse font-mono text-sm font-bold text-fg-inverse"
              aria-hidden="true"
            >cs</span>
            <div class="min-w-0">
              <div class="truncate text-sm font-semibold leading-tight text-fg-strong">
                content-stack
              </div>
              <div class="text-xs text-fg-muted">
                Operator console
              </div>
            </div>
          </div>
        </div>

        <div class="border-b border-subtle px-3 py-3">
          <ProjectSwitcher />
        </div>

        <nav class="min-h-0 flex-1 overflow-y-auto px-3 py-3 [scrollbar-width:thin]">
          <div class="mb-3">
            <RouterLink
              to="/projects"
              class="relative block rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-fast"
              :class="route.path === '/projects'
                ? 'bg-accent-subtle text-accent-fg shadow-xs before:absolute before:bottom-1.5 before:left-1 before:top-1.5 before:w-0.5 before:rounded-full before:bg-accent'
                : 'text-fg-default hover:bg-bg-surface-alt'"
              @click="closeDrawer"
            >
              <span class="block min-w-0 truncate pl-2 font-medium">
                All projects
              </span>
            </RouterLink>
          </div>

          <p
            v-if="projectNavSections.length === 0"
            class="rounded-md border border-dashed border-subtle px-3 py-3 text-sm text-fg-muted"
          >
            Pick a project to see its operating navigation.
          </p>
          <div
            v-else
            class="space-y-3"
          >
            <section
              v-for="section in projectNavSections"
              :key="section.label"
              :aria-label="`${section.label} navigation`"
            >
              <h2 class="mb-0.5 px-3 text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
                {{ section.label }}
              </h2>
              <ul class="space-y-0.5">
                <li
                  v-for="item in section.items"
                  :key="item.to"
                >
                  <RouterLink
                    :to="item.to"
                    :class="navItemClass(item)"
                    :title="item.description"
                    @click="closeDrawer"
                  >
                    <span class="block min-w-0 truncate pl-2 font-medium">
                      {{ item.label }}
                    </span>
                  </RouterLink>
                </li>
              </ul>
            </section>
          </div>
        </nav>

        <div class="border-t border-subtle px-4 py-3">
          <button
            type="button"
            class="inline-flex w-full items-center justify-between rounded-md border border-default bg-bg-surface px-3 py-2 text-xs text-fg-default hover:bg-bg-surface-alt focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            :aria-pressed="theme === 'dark'"
            @click="toggleTheme"
          >
            <span>{{ theme === 'dark' ? 'Dark' : 'Light' }} theme</span>
            <span
              class="h-2 w-2 rounded-full bg-current opacity-50"
              aria-hidden="true"
            />
          </button>
        </div>
      </div>
    </aside>

    <main class="relative min-w-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6 lg:px-8">
      <ul
        v-if="toastItems.length > 0"
        class="pointer-events-none fixed inset-x-4 top-3 z-50 mx-auto flex max-w-md flex-col gap-2 sm:left-auto sm:right-4 sm:mx-0"
        aria-live="polite"
      >
        <li
          v-for="t in toastItems"
          :key="t.id"
          role="status"
          class="pointer-events-auto rounded-md border p-3 text-sm shadow-sm"
          :class="
            t.kind === 'error'
              ? 'border-danger-border bg-danger-subtle text-danger-fg'
              : t.kind === 'success'
                ? 'border-success-border bg-success-subtle text-success-fg'
                : 'border-neutral-border bg-neutral-subtle text-neutral-fg'
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
              class="rounded-xs p-1 text-xs opacity-70 hover:opacity-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-current"
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
        class="rounded-md border border-warning-border bg-warning-subtle p-3 text-sm text-warning-fg"
        role="alert"
      >
        Authenticating with the daemon…
      </div>

      <RouterView />
    </main>
  </div>
</template>
