<script setup lang="ts">
// KvList — semantic <dl>/<dt>/<dd> key/value display.
//
// Used by ProjectDetailView's OverviewTab and other read-only summaries.
// Items are rendered in declaration order; the consumer may format values
// up-front (the component just renders strings/slots).

interface KvItem {
  key: string
  label: string
  value: unknown
}

interface Props {
  items: KvItem[]
  /** When true, lays the rows out two columns wide on md+. */
  twoColumn?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  twoColumn: false,
})

function display(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number') return value.toLocaleString()
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (value instanceof Date) return value.toISOString()
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}
</script>

<template>
  <dl
    class="grid gap-x-6 gap-y-3 text-sm"
    :class="props.twoColumn ? 'sm:grid-cols-[max-content_1fr] md:grid-cols-[max-content_1fr_max-content_1fr]' : 'sm:grid-cols-[max-content_1fr]'"
  >
    <template
      v-for="item in items"
      :key="item.key"
    >
      <dt class="font-medium text-gray-600 dark:text-gray-400">
        {{ item.label }}
      </dt>
      <dd class="text-gray-900 dark:text-gray-100">
        <slot
          :name="`item:${item.key}`"
          :value="item.value"
          :item="item"
        >
          {{ display(item.value) }}
        </slot>
      </dd>
    </template>
  </dl>
</template>
