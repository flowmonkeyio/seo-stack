<script setup lang="ts">
import UiButton from '../ui/UiButton.vue'
import UiCard from '../ui/UiCard.vue'
import UiFormField from '../ui/UiFormField.vue'
import UiJsonBlock from '../ui/UiJsonBlock.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiTextarea from '../ui/UiTextarea.vue'

defineProps<{
  schemaType: string
  schemaJson: string
  valid?: boolean
  error?: string | null
  schemaTypes?: string[]
  saving?: boolean
}>()

defineEmits<{
  (e: 'update:schemaType', value: string): void
  (e: 'update:schemaJson', value: string): void
  (e: 'validate'): void
  (e: 'save'): void
}>()
</script>

<template>
  <UiCard density="compact">
    <template #header>
      <div>
        <h3 class="text-sm font-semibold text-fg-strong">
          Schema editor
        </h3>
        <p class="text-xs text-fg-muted">
          JSON-LD payload and schema.org type.
        </p>
      </div>
      <span
        :class="valid ? 'text-success-fg' : 'text-warning-fg'"
        class="text-xs font-medium"
      >
        {{ valid ? 'Valid' : 'Needs validation' }}
      </span>
    </template>
    <div class="space-y-3">
      <UiFormField
        label="Schema type"
        :error="null"
      >
        <UiSelect
          :model-value="schemaType"
          :options="schemaTypes ?? ['Article', 'BlogPosting', 'FAQPage', 'HowTo']"
          @update:model-value="$emit('update:schemaType', String($event ?? ''))"
        />
      </UiFormField>
      <UiFormField
        label="JSON-LD"
        :error="error"
      >
        <UiTextarea
          :model-value="schemaJson"
          :rows="12"
          class="font-mono"
          @update:model-value="$emit('update:schemaJson', String($event ?? ''))"
        />
      </UiFormField>
      <UiJsonBlock
        :data="schemaJson"
        max-height="16rem"
        wrap
      />
    </div>
    <template #footer>
      <UiButton
        size="sm"
        variant="secondary"
        @click="$emit('validate')"
      >
        Validate
      </UiButton>
      <UiButton
        size="sm"
        variant="primary"
        :loading="saving"
        @click="$emit('save')"
      >
        Save schema
      </UiButton>
    </template>
  </UiCard>
</template>
