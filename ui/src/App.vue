<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="flex min-h-screen flex-col md:flex-row">
    <!-- Sidebar: collapses to a top bar at < md. -->
    <aside
      class="border-b border-gray-200 bg-white md:w-60 md:flex-shrink-0 md:border-b-0 md:border-r dark:border-gray-800 dark:bg-gray-900"
      aria-label="Primary navigation"
    >
      <div class="flex items-center gap-2 px-4 py-4 md:px-6">
        <span
          class="inline-flex h-8 w-8 items-center justify-center rounded bg-gray-900 font-mono text-sm font-bold text-white dark:bg-gray-100 dark:text-gray-900"
          aria-hidden="true"
          >cs</span
        >
        <div>
          <div class="text-sm font-semibold leading-tight">content-stack</div>
          <div class="text-xs text-gray-500 dark:text-gray-400">M0 scaffold</div>
        </div>
      </div>
      <nav class="px-2 pb-4 md:px-4">
        <ul class="space-y-1 text-sm">
          <li>
            <RouterLink
              to="/"
              class="block rounded px-3 py-2 text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800"
              active-class="bg-gray-100 font-medium text-gray-900 dark:bg-gray-800 dark:text-white"
            >
              Home
            </RouterLink>
          </li>
        </ul>
      </nav>
    </aside>

    <!-- Main content -->
    <main class="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
      <RouterView />
    </main>
  </div>
</template>
