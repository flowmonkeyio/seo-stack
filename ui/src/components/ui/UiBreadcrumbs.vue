<!--
  UiBreadcrumbs — compact breadcrumb trail rendered inside UiPageHeader.
  Pass `to` for navigable ancestors; omit it for the current page.
-->
<script setup lang="ts">
import UiIcon from './UiIcon.vue';

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
          class="focus-ring rounded-xs text-fg-muted transition-colors duration-fast hover:text-fg-default"
        >
          {{ item.label }}
        </RouterLink>
        <span
          v-else
          class="block max-w-[28ch] truncate"
          :class="idx === items.length - 1 ? 'font-medium text-fg-default' : 'text-fg-muted'"
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
        <UiIcon
          name="chevron-right"
          class="h-3 w-3"
          aria-hidden="true"
        />
      </li>
    </template>
  </ol>
</template>
