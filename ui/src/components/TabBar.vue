<script setup lang="ts">
// TabBar — accessible tablist with arrow-key navigation.
//
// `tabs` is an ordered list of `{ key, label, count?, disabled? }` items.
// `activeKey` selects which tab is rendered as `aria-selected="true"`. The
// host listens to `change` to swap content. Vertical accent bar marks
// the active tab; pending/M5.B tabs can pass `count` for a numeric badge.

import { ref, watch } from 'vue'

interface Tab {
  key: string
  label: string
  count?: number
  disabled?: boolean
}

interface Props {
  tabs: Tab[]
  activeKey: string
  /** Aria-label for the surrounding tablist. */
  ariaLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  ariaLabel: 'Tabs',
})

const emit = defineEmits<{
  (e: 'change', key: string): void
}>()

const tabRefs = ref<HTMLButtonElement[]>([])
const focusIdx = ref<number>(0)

watch(
  () => props.activeKey,
  (key) => {
    const i = props.tabs.findIndex((t) => t.key === key)
    if (i >= 0) focusIdx.value = i
  },
  { immediate: true },
)

function focusTab(i: number): void {
  focusIdx.value = i
  const el = tabRefs.value[i]
  if (el) el.focus()
}

function nextEnabled(start: number, dir: 1 | -1): number {
  const n = props.tabs.length
  for (let step = 1; step <= n; step++) {
    const i = (start + dir * step + n) % n
    if (!props.tabs[i].disabled) return i
  }
  return start
}

function onKeydown(e: KeyboardEvent, idx: number): void {
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
    e.preventDefault()
    focusTab(nextEnabled(idx, 1))
  } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    e.preventDefault()
    focusTab(nextEnabled(idx, -1))
  } else if (e.key === 'Home') {
    e.preventDefault()
    focusTab(nextEnabled(-1, 1))
  } else if (e.key === 'End') {
    e.preventDefault()
    focusTab(nextEnabled(props.tabs.length, -1))
  } else if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
    e.preventDefault()
    onSelect(props.tabs[idx])
  }
}

function onSelect(tab: Tab): void {
  if (tab.disabled) return
  if (tab.key === props.activeKey) return
  emit('change', tab.key)
}
</script>

<template>
  <div
    role="tablist"
    :aria-label="props.ariaLabel"
    class="flex flex-wrap gap-1 border-b border-gray-200 dark:border-gray-800"
  >
    <button
      v-for="(tab, i) in props.tabs"
      :id="`cs-tab-${tab.key}`"
      :key="tab.key"
      :ref="(el) => (tabRefs[i] = el as HTMLButtonElement)"
      type="button"
      role="tab"
      :aria-selected="tab.key === props.activeKey"
      :aria-controls="`cs-tabpanel-${tab.key}`"
      :tabindex="tab.key === props.activeKey ? 0 : -1"
      :disabled="tab.disabled"
      class="relative -mb-px px-3 py-2 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
      :class="
        tab.key === props.activeKey
          ? 'border-b-2 border-blue-600 text-gray-900 dark:text-white'
          : 'border-b-2 border-transparent text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white'
      "
      @click="onSelect(tab)"
      @keydown="onKeydown($event, i)"
    >
      {{ tab.label }}
      <span
        v-if="typeof tab.count === 'number'"
        class="ml-1 inline-block min-w-[1.25rem] rounded-full bg-gray-100 px-1.5 py-0 text-center text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-200"
      >
        {{ tab.count }}
      </span>
    </button>
  </div>
</template>
