<!--
  UiDialog — modal dialog. Centered, focus-trapped, scroll-locked.

  Always:
    - title (accessible name)
    - explicit close button
    - footer with primary / secondary actions

  For yes/no confirmations, use UiConfirmDialog.
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch, nextTick } from 'vue';
import UiIconButton from './UiIconButton.vue';

export interface UiDialogProps {
  modelValue: boolean;
  title?: string;
  description?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  /** Hide the X. Use only when dismiss requires explicit user action. */
  hideClose?: boolean;
  /** Disable backdrop click-to-close. */
  staticBackdrop?: boolean;
  /** Disable Escape-to-close. */
  noEscape?: boolean;
  /** Wider, scrollable body for forms. */
  scrollBody?: boolean;
}

const props = withDefaults(defineProps<UiDialogProps>(), { size: 'md' });

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void;
  (e: 'close'): void;
}>();

const dialogRef = ref<HTMLDivElement | null>(null);
const previousFocus = ref<HTMLElement | null>(null);

function close() {
  emit('update:modelValue', false);
  emit('close');
}

function onKey(ev: KeyboardEvent) {
  if (!props.modelValue) return;
  if (ev.key === 'Escape' && !props.noEscape) {
    close();
    ev.stopPropagation();
  } else if (ev.key === 'Tab') {
    trapFocus(ev);
  }
}

function trapFocus(ev: KeyboardEvent) {
  const node = dialogRef.value;
  if (!node) return;
  const focusables = node.querySelectorAll<HTMLElement>(
    'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
  );
  if (!focusables.length) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (ev.shiftKey && document.activeElement === first) {
    last.focus();
    ev.preventDefault();
  } else if (!ev.shiftKey && document.activeElement === last) {
    first.focus();
    ev.preventDefault();
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      previousFocus.value = document.activeElement as HTMLElement;
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', onKey);
      await nextTick();
      const target = dialogRef.value?.querySelector<HTMLElement>('[data-autofocus]')
        ?? dialogRef.value?.querySelector<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
      target?.focus();
    } else {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', onKey);
      previousFocus.value?.focus?.();
    }
  },
  { immediate: false }
);

onBeforeUnmount(() => {
  document.body.style.overflow = '';
  window.removeEventListener('keydown', onKey);
});

const sizeClass = computed(() => ({
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
}[props.size]));
</script>

<template>
  <transition
    enter-active-class="transition-opacity duration-base ease-enter"
    enter-from-class="opacity-0"
    leave-active-class="transition-opacity duration-fast ease-exit"
    leave-to-class="opacity-0"
  >
    <div
      v-if="modelValue"
      class="ui-dialog__overlay fixed inset-0 z-overlay bg-bg-overlay flex items-center justify-center p-4"
      @click.self="!staticBackdrop && close()"
    >
      <transition
        enter-active-class="transition duration-base ease-enter"
        enter-from-class="opacity-0 scale-[0.97]"
        leave-active-class="transition duration-fast ease-exit"
        leave-to-class="opacity-0 scale-[0.97]"
      >
        <div
          v-if="modelValue"
          ref="dialogRef"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="title ? 'ui-dialog-title' : undefined"
          :aria-describedby="description ? 'ui-dialog-desc' : undefined"
          :class="[
            'ui-dialog z-modal w-full rounded-lg bg-bg-surface shadow-lg border border-default flex flex-col max-h-[calc(100vh-2rem)]',
            sizeClass,
          ]"
        >
          <header v-if="title || $slots.header || !hideClose" class="ui-dialog__header flex items-start justify-between gap-3 px-5 py-4 border-b border-subtle">
            <div class="min-w-0">
              <slot name="header">
                <h2 v-if="title" id="ui-dialog-title" class="t-h1 text-fg-strong">{{ title }}</h2>
                <p v-if="description" id="ui-dialog-desc" class="text-sm text-fg-muted mt-1">{{ description }}</p>
              </slot>
            </div>
            <UiIconButton
              v-if="!hideClose"
              aria-label="Close dialog"
              size="sm"
              variant="ghost"
              @click="close"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg>
            </UiIconButton>
          </header>
          <div :class="[
            'ui-dialog__body px-5 py-4',
            scrollBody && 'overflow-y-auto',
          ]">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="ui-dialog__footer flex items-center justify-end gap-2 px-5 py-3 border-t border-subtle bg-bg-surface-alt rounded-b-lg">
            <slot name="footer" :close="close" />
          </footer>
        </div>
      </transition>
    </div>
  </transition>
</template>
