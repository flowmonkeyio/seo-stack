<script setup lang="ts">
// MarkdownEditor — textarea-based editor with optimistic concurrency.
//
// Per PLAN.md L803-L811 saves carry an `If-Match: <updated_at iso>`
// header. On 412 from the server we surface a "remote changed" prompt
// with reload / overwrite options. The full WYSIWYG experience is out of
// M5 scope; M5 is a careful textarea + preview toggle.
//
// Features:
//   - v-model:value 2-way binding
//   - Auto-save every 5s if dirty (debounced)
//   - Manual save (Cmd+S / Ctrl+S)
//   - Word + character count footer
//   - Conflict resolution flow on 412
//   - Optional `preview` toggle that swaps the textarea for a
//     <MarkdownView> render of the current draft

import { computed, onBeforeUnmount, ref, watch } from 'vue'

import MarkdownView from '@/components/MarkdownView.vue'

interface Props {
  value: string
  /** Optimistic concurrency token — last-known `updated_at` ISO string. */
  updatedAt?: string | null
  /** Optional save handler — receives the new body + ifMatch token. */
  onSave?: (body: string, ifMatch: string | null) => Promise<{ updated_at?: string }>
  /** Disable interaction while a save is in flight. */
  saving?: boolean
  /** Auto-save debounce in ms. 0 disables auto-save. */
  autoSaveMs?: number
  /** Aria label for the textarea. */
  ariaLabel?: string
  /** Optional placeholder for empty content. */
  placeholder?: string
  /** Render preview tab as default. */
  showPreview?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  updatedAt: null,
  onSave: undefined,
  saving: false,
  autoSaveMs: 5_000,
  ariaLabel: 'Markdown editor',
  placeholder: 'Write Markdown here…',
  showPreview: false,
})

const emit = defineEmits<{
  (e: 'update:value', value: string): void
  (e: 'saved', updatedAt: string | undefined): void
  (e: 'conflict', payload: { current: string }): void
  (e: 'error', err: Error): void
}>()

const localValue = ref<string>(props.value)
const dirty = ref<boolean>(false)
const lastSavedAt = ref<string | null>(props.updatedAt)
const previewMode = ref<boolean>(props.showPreview)
const conflictOpen = ref<boolean>(false)
const conflictRemote = ref<string>('')

let autoSaveTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => props.value,
  (next) => {
    if (next !== localValue.value && !dirty.value) {
      localValue.value = next
    }
    lastSavedAt.value = props.updatedAt
  },
)

function clearAutoSave(): void {
  if (autoSaveTimer !== null) {
    clearTimeout(autoSaveTimer)
    autoSaveTimer = null
  }
}

function scheduleAutoSave(): void {
  if (props.autoSaveMs <= 0) return
  if (!props.onSave) return
  clearAutoSave()
  autoSaveTimer = setTimeout(() => {
    void save({ source: 'auto' })
  }, props.autoSaveMs)
}

function onInput(e: Event): void {
  const value = (e.target as HTMLTextAreaElement).value
  localValue.value = value
  dirty.value = true
  emit('update:value', value)
  scheduleAutoSave()
}

async function save(opts: { source: 'manual' | 'auto' } = { source: 'manual' }): Promise<void> {
  if (!props.onSave) return
  if (!dirty.value && opts.source === 'auto') return
  clearAutoSave()
  try {
    const res = await props.onSave(localValue.value, lastSavedAt.value)
    dirty.value = false
    if (res?.updated_at) {
      lastSavedAt.value = res.updated_at
    }
    emit('saved', res?.updated_at)
  } catch (err) {
    if (err && typeof err === 'object' && 'status' in err && (err as { status: number }).status === 412) {
      // Surface conflict to caller; UI shows the remote-changed prompt.
      conflictOpen.value = true
      const detail = (err as { body?: { current_md?: string } }).body
      if (detail?.current_md) conflictRemote.value = detail.current_md
      emit('conflict', { current: conflictRemote.value })
      return
    }
    emit('error', err instanceof Error ? err : new Error(String(err)))
  }
}

function manualSave(): void {
  void save({ source: 'manual' })
}

function onKeydown(e: KeyboardEvent): void {
  if ((e.metaKey || e.ctrlKey) && e.key === 's') {
    e.preventDefault()
    manualSave()
  }
}

function reloadFromRemote(): void {
  if (conflictRemote.value) {
    localValue.value = conflictRemote.value
    emit('update:value', conflictRemote.value)
    dirty.value = false
    conflictOpen.value = false
  } else {
    conflictOpen.value = false
  }
}

function overwriteRemote(): void {
  // Bump our cached `updated_at` to the server's so the next save passes
  // the precondition. Caller must pass a fresh `updatedAt` after this
  // resolves; we just trust the in-memory text and re-attempt save.
  conflictOpen.value = false
  lastSavedAt.value = null
  void save({ source: 'manual' })
}

onBeforeUnmount(clearAutoSave)

const wordCount = computed<number>(() => {
  const trimmed = localValue.value.trim()
  if (trimmed.length === 0) return 0
  return trimmed.split(/\s+/).length
})

const charCount = computed<number>(() => localValue.value.length)
</script>

<template>
  <div class="cs-markdown-editor overflow-hidden rounded-md border border-default bg-bg-surface shadow-xs">
    <div class="flex flex-wrap items-center justify-between gap-2 border-b border-subtle bg-bg-surface-alt px-3 py-2 text-sm">
      <div class="inline-flex overflow-hidden rounded-sm border border-default bg-bg-surface">
        <button
          type="button"
          class="h-8 px-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          :class="
            previewMode
              ? 'text-fg-muted hover:bg-bg-surface-alt'
              : 'bg-accent text-fg-on-accent font-medium'
          "
          @click="previewMode = false"
        >
          Edit
        </button>
        <button
          type="button"
          class="h-8 border-l border-subtle px-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          :class="
            previewMode
              ? 'bg-accent text-fg-on-accent font-medium'
              : 'text-fg-muted hover:bg-bg-surface-alt'
          "
          @click="previewMode = true"
        >
          Preview
        </button>
      </div>
      <button
        v-if="props.onSave"
        type="button"
        class="h-8 rounded-sm bg-accent px-3 text-sm font-medium text-fg-on-accent hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="props.saving || !dirty"
        @click="manualSave"
      >
        {{ props.saving ? 'Saving…' : 'Save' }}
      </button>
    </div>

    <div
      v-if="!previewMode"
      class="p-3"
    >
      <textarea
        :value="localValue"
        :aria-label="props.ariaLabel"
        :placeholder="props.placeholder"
        :disabled="props.saving"
        class="block min-h-[28rem] w-full resize-y rounded-sm border border-default bg-bg-surface p-3 font-mono text-[13px] leading-6 text-fg-default shadow-inset focus:border-focus focus:outline-none focus:ring-1 focus:ring-focus"
        @input="onInput"
        @keydown="onKeydown"
      />
    </div>
    <div
      v-else
      class="m-3 min-h-[28rem] rounded-sm border border-default bg-bg-surface p-4"
    >
      <MarkdownView
        :source="localValue"
        empty-message="(empty draft)"
      />
    </div>

    <div class="flex items-center justify-between border-t border-subtle bg-bg-surface-alt px-3 py-2 text-xs text-fg-muted">
      <span>
        <span aria-live="polite">{{ wordCount }} words</span> · {{ charCount }} chars
      </span>
      <span
        v-if="dirty"
        class="text-warning-fg"
      >unsaved changes</span>
      <span
        v-else-if="lastSavedAt"
        class="text-success-fg"
      >
        saved at {{ lastSavedAt }}
      </span>
    </div>

    <div
      v-if="conflictOpen"
      class="mt-2 rounded-md border border-warning-border bg-warning-subtle p-3 text-sm"
      role="alertdialog"
      aria-labelledby="cs-md-conflict-title"
    >
      <div
        id="cs-md-conflict-title"
        class="mb-1 font-medium text-warning-fg"
      >
        Remote copy changed
      </div>
      <p class="mb-2 text-warning-fg">
        Someone else updated this content while you were editing. Reload to
        replace your draft with the remote version, or overwrite to push
        your local changes anyway.
      </p>
      <div class="flex gap-2">
        <button
          type="button"
          class="rounded-sm border border-warning-border px-3 py-1 text-sm font-medium text-warning-fg hover:bg-bg-surface"
          @click="reloadFromRemote"
        >
          Reload remote
        </button>
        <button
          type="button"
          class="rounded-sm bg-warning px-3 py-1 text-sm font-medium text-fg-on-accent hover:opacity-90"
          @click="overwriteRemote"
        >
          Overwrite
        </button>
      </div>
    </div>
  </div>
</template>
