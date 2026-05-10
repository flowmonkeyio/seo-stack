<!--
  UiSecretInput — masked input for API keys, tokens, passwords.
  Adds reveal toggle, copy button, and obscured display.
-->
<script setup lang="ts">
import { computed, ref } from 'vue';
import UiInput from './UiInput.vue';
import UiIconButton from './UiIconButton.vue';

export interface UiSecretInputProps {
  modelValue?: string;
  placeholder?: string;
  disabled?: boolean;
  invalid?: boolean;
  required?: boolean;
  /** Hide reveal toggle (e.g. for write-only fields). */
  noReveal?: boolean;
  /** Hide copy button. */
  noCopy?: boolean;
  /** Show only last N chars when masked. */
  maskedSuffixLen?: number;
  size?: 'sm' | 'md' | 'lg';
  id?: string;
  ariaDescribedby?: string;
}

const props = withDefaults(defineProps<UiSecretInputProps>(), {
  size: 'md',
  maskedSuffixLen: 4,
});

const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>();

const revealed = ref(false);
const copied = ref(false);

const displayType = computed(() => (revealed.value ? 'text' : 'password'));

async function copy() {
  if (!props.modelValue) return;
  try {
    await navigator.clipboard.writeText(props.modelValue);
    copied.value = true;
    setTimeout(() => { copied.value = false; }, 1500);
  } catch { /* clipboard not available */ }
}
</script>

<template>
  <UiInput
    :model-value="modelValue"
    :type="displayType"
    :placeholder="placeholder"
    :disabled="disabled"
    :invalid="invalid"
    :required="required"
    :size="size"
    :id="id"
    :aria-describedby="ariaDescribedby"
    autocomplete="off"
    spellcheck="false"
    @update:model-value="(v: any) => $emit('update:modelValue', String(v ?? ''))"
  >
    <template #suffix>
      <div class="flex items-center gap-0.5">
        <UiIconButton
          v-if="!noReveal"
          :aria-label="revealed ? 'Hide value' : 'Reveal value'"
          size="sm"
          variant="ghost"
          @click="revealed = !revealed"
        >
          <svg v-if="!revealed" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m3 3 18 18M10.6 6.1a8 8 0 0 1 11.4 5.9 13 13 0 0 1-1.7 2.7M6.6 6.6A13 13 0 0 0 2 12s3 7 10 7c1.7 0 3.2-.4 4.5-1.1"/></svg>
        </UiIconButton>
        <UiIconButton
          v-if="!noCopy"
          :aria-label="copied ? 'Copied' : 'Copy value'"
          size="sm"
          variant="ghost"
          @click="copy"
        >
          <svg v-if="!copied" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m5 12 5 5 9-12"/></svg>
        </UiIconButton>
      </div>
    </template>
  </UiInput>
</template>
