<script setup lang="ts">
import DataTable from '@/components/DataTable.vue'
import type { DataTableColumn } from '@/components/types'
import type { TrackerTicket } from '@/lib/task-tracker/types'

import TrackerStatusBadge from './TrackerStatusBadge.vue'

defineProps<{
  tickets: TrackerTicket[]
  columns: DataTableColumn<TrackerTicket>[]
  loading: boolean
  selectedTicketId: number | null
}>()

defineEmits<{
  (e: 'rowClick', row: TrackerTicket): void
}>()
</script>

<template>
  <div class="tracker-ticket-table">
    <DataTable
      :items="tickets"
      :columns="columns"
      :loading="loading"
      interactive
      :selected-id="selectedTicketId"
      aria-label="Tracker tickets"
      empty-message="No tickets match the current filters."
      @row-click="$emit('rowClick', $event as TrackerTicket)"
    >
      <template #cell:key="{ row }">
        <span class="font-mono text-xs text-fg-default">{{ (row as TrackerTicket).key }}</span>
      </template>
      <template #cell:task_key="{ row }">
        <span class="font-mono text-xs text-fg-muted">{{ (row as TrackerTicket).task_key }}</span>
      </template>
      <template #cell:status="{ row }">
        <TrackerStatusBadge :status="(row as TrackerTicket).status" />
      </template>
    </DataTable>
  </div>
</template>

<style scoped>
.tracker-ticket-table {
  flex: 1 1 auto;
  min-width: 0;
}
</style>
