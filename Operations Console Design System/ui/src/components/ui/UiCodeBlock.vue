<!--
  UiCodeBlock — read-only code display with optional copy button + line numbers.
  Use UiJsonBlock for JSON-specific niceties.
-->
<script setup lang="ts">
import { computed, ref } from 'vue';
import UiIconButton from './UiIconButton.vue';

defineProps<{
  code: string;
  language?: string;
  /** Show line numbers. */
  numbered?: boolean;
  /** Wrap long lines. Default false (horizontal scroll). */
  wrap?: boolean;
  /** Show copy button. */
  copyable?: boolean;
  /** Compact: smaller font + padding. */
  density?: 'compact' | 'comfortable';
  /** Maximum visible height (CSS). */
  maxHeight?: string;
  ariaLabel?: string;
}>();

const copied = ref(false);

async function copy(code: string) {
  try {
    await navigator.clipboard.writeText(code);
    copied.value = true;
    setTimeout(() => { copied.value = false; }, 1500);
  } catch { /* noop */ }
}
</script>

<template>
  <div
    :class="[
      'ui-codeblock relative rounded-md border border-subtle bg-bg-sunken font-mono text-fg-default',
      density === 'comfortable' ? 'text-sm' : 'text-xs',
    ]"
    :aria-label="ariaLabel"
  >
    <div v-if="language || copyable" class="ui-codeblock__chrome flex items-center justify-between px-3 py-1.5 border-b border-subtle">
      <span class="text-2xs uppercase tracking-wider text-fg-subtle font-sans font-semibold">{{ language }}</span>
      <UiIconButton
        v-if="copyable"
        :aria-label="copied ? 'Copied' : 'Copy code'"
        size="sm"
        variant="ghost"
        @click="copy(code)"
      >
        <svg v-if="!copied" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>
        <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m5 12 5 5 9-12"/></svg>
      </UiIconButton>
    </div>
    <pre
      :class="[
        'ui-codeblock__pre overflow-x-auto m-0',
        wrap ? 'whitespace-pre-wrap break-all' : 'whitespace-pre',
        density === 'comfortable' ? 'p-4' : 'p-3',
      ]"
      :style="{ maxHeight }"
    ><code><template v-if="numbered"><span
            v-for="(line, i) in code.split('\n')"
            :key="i"
            class="ui-codeblock__line flex"
          ><span class="ui-codeblock__lineno select-none text-fg-disabled tabular-nums pr-3 text-right" style="min-width: 2.5em">{{ i + 1 }}</span><span class="flex-1">{{ line || ' ' }}</span></span></template><template v-else>{{ code }}</template></code></pre>
  </div>
</template>
