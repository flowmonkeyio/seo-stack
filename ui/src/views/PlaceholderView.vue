<script setup lang="ts">
// PlaceholderView — generic shell used by views that land in M5.B / M5.C.
// Displays a heading + milestone tag so the route is browseable while
// the real implementation is incoming.

import {
  UiBadge,
  UiEmptyState,
  UiPageHeader,
  UiPageShell,
} from '@/components/ui'

interface Props {
  title: string
  milestone: string
  description?: string
}

withDefaults(defineProps<Props>(), {
  description: '',
})
</script>

<template>
  <UiPageShell>
    <UiPageHeader
      :title="title"
      :description="description || `This view is part of milestone ${milestone}. The route is wired; the real content lands when ${milestone} ships.`"
    >
      <template #titleMeta>
        <UiBadge
          tone="warning"
          variant="subtle"
        >
          coming in {{ milestone }}
        </UiBadge>
      </template>
    </UiPageHeader>
    <UiEmptyState
      title="Not implemented yet"
      :description="description || `Milestone ${milestone} owns this screen.`"
      size="md"
    />
  </UiPageShell>
</template>
