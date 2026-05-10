<!--
  UiBreadcrumbs — compact breadcrumb trail rendered inside UiPageHeader.
  Pass `to` for navigable ancestors; omit it for the current page.
-->
<script setup lang="ts">
export interface UiBreadcrumbItem {
  label: string;
  to?: string;
}

defineProps<{
  items: UiBreadcrumbItem[];
}>();
</script>

<template>
  <ol class="ui-breadcrumbs flex min-w-0 flex-wrap items-center gap-1 text-xs">
    <template
      v-for="(item, idx) in items"
      :key="`${item.label}-${idx}`"
    >
      <li class="min-w-0">
        <RouterLink
          v-if="item.to && idx < items.length - 1"
          :to="item.to"
          class="text-fg-link hover:underline"
        >
          {{ item.label }}
        </RouterLink>
        <span
          v-else
          class="block max-w-[28ch] truncate text-fg-muted"
          :aria-current="idx === items.length - 1 ? 'page' : undefined"
        >
          {{ item.label }}
        </span>
      </li>
      <li
        v-if="idx < items.length - 1"
        aria-hidden="true"
        class="text-fg-subtle"
      >
        /
      </li>
    </template>
  </ol>
</template>
