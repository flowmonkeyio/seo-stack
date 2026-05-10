<!--
  UiDescriptionList — semantic <dl> for key-value metadata blocks.
  Replaces ad-hoc 2-col grids. Term/value pairs render as horizontal rows
  by default; vertical for narrow layouts.

  Items prop or slot:
    <UiDescriptionList :items="[{label:'Project', value:'…'}]" />
    or use <UiDescriptionItem label="…">value</UiDescriptionItem> children.
-->
<script setup lang="ts">
export interface DLItem {
  label: string;
  /** Plain-string value. For rich content use the slot form instead. */
  value?: string | number | null;
  /** Render value with mono font (IDs, hashes). */
  mono?: boolean;
  /** Help text under the label. */
  hint?: string;
  /** Optional render override slot name when used with <UiDescriptionList>. */
  slot?: string;
}

defineProps<{
  items?: DLItem[];
  /** Layout: rows (label left, value right) or stacked. */
  layout?: 'rows' | 'stacked' | 'grid';
  /** When `grid`, number of columns. */
  columns?: 1 | 2 | 3 | 4;
  density?: 'compact' | 'comfortable';
  /** Force value column to align right (numeric). */
  numeric?: boolean;
  ariaLabel?: string;
}>();

const dashIfNull = (v: unknown) => (v === null || v === undefined || v === '' ? '—' : v);
</script>

<template>
  <dl
    :aria-label="ariaLabel"
    :class="[
      'ui-description-list',
      layout === 'stacked' && 'flex flex-col gap-3',
      layout === 'grid' && `grid grid-cols-${columns ?? 2} gap-x-6 gap-y-3`,
      (!layout || layout === 'rows') && 'flex flex-col',
    ]"
  >
    <template v-if="items">
      <div
        v-for="item in items"
        :key="item.label"
        :class="[
          'ui-description-list__item',
          (!layout || layout === 'rows') && [
            'grid grid-cols-[max-content_1fr] items-baseline gap-3',
            density === 'compact' ? 'py-1' : 'py-1.5',
            'border-b border-subtle last:border-b-0',
          ],
          layout === 'stacked' && 'flex flex-col gap-0.5',
          layout === 'grid' && 'flex flex-col gap-0.5 min-w-0',
        ]"
      >
        <dt
          :class="[
            'text-xs font-medium uppercase text-fg-subtle',
            (!layout || layout === 'rows') && 'min-w-[8rem]',
          ]"
        >
          {{ item.label }}
          <p
            v-if="item.hint"
            class="text-2xs font-normal normal-case text-fg-disabled mt-0.5"
          >
            {{ item.hint }}
          </p>
        </dt>
        <dd
          :class="[
            'text-sm text-fg-default min-w-0 break-words',
            item.mono && 'font-mono text-xs',
            numeric && 'text-right tabular-nums',
          ]"
        >
          <slot
            :name="item.slot ?? item.label"
            :item="item"
          >
            {{ dashIfNull(item.value) }}
          </slot>
        </dd>
      </div>
    </template>
    <slot v-else />
  </dl>
</template>
