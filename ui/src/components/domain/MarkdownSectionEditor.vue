<script setup lang="ts">
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { computed, ref } from 'vue'

import UiButton from '../ui/UiButton.vue'
import UiButtonGroup from '../ui/UiButtonGroup.vue'
import UiCard from '../ui/UiCard.vue'
import UiFormField from '../ui/UiFormField.vue'
import UiIconButton from '../ui/UiIconButton.vue'
import UiTextarea from '../ui/UiTextarea.vue'
import UiToolbar from '../ui/UiToolbar.vue'

const props = withDefaults(
  defineProps<{
    modelValue: string
    title: string
    sectionKey?: string
    help?: string
    placeholder?: string
    previewHtml?: string | null
    dirty?: boolean
    saved?: boolean
    saving?: boolean
    disabled?: boolean
    minRows?: number
    maxRows?: number
    error?: string | null
  }>(),
  {
    sectionKey: undefined,
    help: undefined,
    placeholder: undefined,
    previewHtml: null,
    minRows: 12,
    maxRows: 28,
    dirty: false,
    saved: false,
    saving: false,
    disabled: false,
    error: null,
  },
)

defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'save'): void
  (e: 'revert'): void
  (e: 'improve'): void
  (e: 'insert', marker: 'h2' | 'h3' | 'bold' | 'link' | 'citation'): void
}>()

const mode = ref<'write' | 'preview'>('write')

const wordCount = computed(() => {
  const words = props.modelValue.trim().match(/\S+/g)
  return words?.length ?? 0
})

const sanitizedPreview = computed(() => {
  const html =
    props.previewHtml ??
    (marked.parse(props.modelValue || '', {
      async: false,
      gfm: true,
      breaks: false,
    }) as string)
  return DOMPurify.sanitize(html)
})
</script>

<template>
  <UiCard
    density="compact"
    :aria-label="title"
  >
    <template #header>
      <div class="min-w-0">
        <h3 class="truncate text-sm font-semibold text-fg-strong">
          {{ title }}
        </h3>
        <p class="font-mono text-xs text-fg-muted">
          {{ sectionKey ?? 'markdown-section' }} · {{ wordCount }} words
        </p>
      </div>
      <UiButtonGroup aria-label="Editor mode">
        <UiButton
          size="sm"
          :variant="mode === 'write' ? 'primary' : 'secondary'"
          @click="mode = 'write'"
        >
          Write
        </UiButton>
        <UiButton
          size="sm"
          :variant="mode === 'preview' ? 'primary' : 'secondary'"
          @click="mode = 'preview'"
        >
          Preview
        </UiButton>
      </UiButtonGroup>
    </template>

    <div class="space-y-3">
      <UiToolbar
        aria-label="Markdown tools"
        density="compact"
      >
        <UiIconButton
          aria-label="Insert H2"
          size="sm"
          variant="ghost"
          @click="$emit('insert', 'h2')"
        >
          H2
        </UiIconButton>
        <UiIconButton
          aria-label="Insert H3"
          size="sm"
          variant="ghost"
          @click="$emit('insert', 'h3')"
        >
          H3
        </UiIconButton>
        <UiIconButton
          aria-label="Bold"
          size="sm"
          variant="ghost"
          @click="$emit('insert', 'bold')"
        >
          B
        </UiIconButton>
        <UiIconButton
          aria-label="Insert link"
          size="sm"
          variant="ghost"
          @click="$emit('insert', 'link')"
        >
          ↗
        </UiIconButton>
        <UiIconButton
          aria-label="Insert citation marker"
          size="sm"
          variant="ghost"
          @click="$emit('insert', 'citation')"
        >
          [1]
        </UiIconButton>

        <template #right>
          <UiButton
            size="sm"
            variant="ghost"
            :disabled="disabled"
            @click="$emit('improve')"
          >
            Improve
          </UiButton>
        </template>
      </UiToolbar>

      <UiFormField
        :label="title"
        hide-label
        :help="help"
        :error="error"
        :dirty="dirty"
        :saved="saved"
      >
        <UiTextarea
          v-if="mode === 'write'"
          :model-value="modelValue"
          :rows="minRows"
          :max-rows="maxRows"
          auto-resize
          resize="vertical"
          class="font-mono"
          :placeholder="placeholder ?? 'Write this section in Markdown...'"
          :disabled="disabled"
          @update:model-value="$emit('update:modelValue', $event)"
        />
        <!-- eslint-disable vue/no-v-html -->
        <div
          v-else
          class="cs-md-preview rounded-sm border border-default bg-bg-surface px-4 py-3 text-fg-default"
          v-html="sanitizedPreview"
        />
        <!-- eslint-enable vue/no-v-html -->
      </UiFormField>
    </div>

    <template #footer>
      <UiButton
        size="sm"
        variant="ghost"
        :disabled="disabled || saving"
        @click="$emit('revert')"
      >
        Revert
      </UiButton>
      <UiButton
        size="sm"
        variant="primary"
        :disabled="disabled"
        :loading="saving"
        @click="$emit('save')"
      >
        Save section
      </UiButton>
    </template>
  </UiCard>
</template>

<style scoped>
.cs-md-preview {
  font-size: var(--fs-sm);
  line-height: var(--lh-sm);
}

.cs-md-preview :deep(h2),
.cs-md-preview :deep(h3) {
  color: var(--color-fg-strong);
  font-weight: var(--fw-semibold);
  margin: 0.8rem 0 0.35rem;
}

.cs-md-preview :deep(p),
.cs-md-preview :deep(ul),
.cs-md-preview :deep(ol) {
  margin: 0.5rem 0;
}

.cs-md-preview :deep(ul),
.cs-md-preview :deep(ol) {
  padding-left: 1.25rem;
}

.cs-md-preview :deep(a) {
  color: var(--color-fg-link);
  text-decoration: underline;
  text-underline-offset: 2px;
}
</style>
