<script setup lang="ts">
// VoiceTab — read-only voice profile visibility.

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import DataTable from '@/components/DataTable.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import { UiBadge, UiButton, UiEmptyState, UiSectionHeader } from '@/components/ui'
import { apiFetch, formatApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import type { components } from '@/api'
import type { DataTableColumn } from '@/components/types'

type Voice = components['schemas']['VoiceProfileOut']
type VoicesPage = components['schemas']['PageResponse_VoiceProfileOut_']

const route = useRoute()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const voices = ref<Voice[]>([])
const loading = ref(false)
const selectedVoiceId = ref<number | null>(null)

const defaultVoice = computed(() => voices.value.find((voice) => voice.is_default) ?? null)
const selectedVoice = computed(() => {
  return (
    voices.value.find((voice) => voice.id === selectedVoiceId.value) ??
    defaultVoice.value ??
    voices.value[0] ??
    null
  )
})
const configuredVoices = computed(() =>
  voices.value.filter((voice) => (voice.voice_md ?? '').trim().length > 0),
)

const columns: DataTableColumn<Voice>[] = [
  { key: 'name', label: 'Name' },
  { key: 'is_default', label: 'Role', format: (value) => (value ? 'Default' : 'Variant') },
  { key: 'version', label: 'Version' },
  {
    key: 'created_at',
    label: 'Created',
    format: (value) => (value ? new Date(String(value)).toLocaleString() : '-'),
  },
]

async function loadVoices(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  loading.value = true
  try {
    const res = await apiFetch<VoicesPage>(
      `/api/v1/projects/${projectId.value}/voice/variants?limit=200`,
    )
    voices.value = res.items ?? []
    if (selectedVoiceId.value && !voices.value.some((voice) => voice.id === selectedVoiceId.value)) {
      selectedVoiceId.value = null
    }
  } catch (err) {
    toasts.error('Failed to load voices', formatApiError(err))
  } finally {
    loading.value = false
  }
}

function selectVoice(voice: Voice): void {
  selectedVoiceId.value = voice.id
}

onMounted(loadVoices)
watch(projectId, loadVoices)
</script>

<template>
  <section class="space-y-6">
    <UiSectionHeader
      title="Voice profiles"
      description="Read-only view of the editorial voice inventory the agent can use during drafting and editing."
    >
      <template #actions>
        <UiButton
          size="sm"
          variant="secondary"
          :disabled="loading"
          @click="loadVoices"
        >
          {{ loading ? 'Refreshing...' : 'Refresh' }}
        </UiButton>
      </template>
    </UiSectionHeader>

    <div class="grid gap-3 md:grid-cols-3">
      <div class="rounded-md border border-default bg-bg-surface p-3 shadow-xs">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          Default profile
        </p>
        <p class="mt-2 text-sm font-semibold text-fg-strong">
          {{ defaultVoice?.name ?? 'Not selected' }}
        </p>
        <p class="mt-1 text-xs text-fg-muted">
          The default profile is the agent's first choice when a procedure has no override.
        </p>
      </div>
      <div class="rounded-md border border-default bg-bg-surface p-3 shadow-xs">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          Profiles
        </p>
        <p class="mt-2 text-sm font-semibold text-fg-strong">
          {{ voices.length }}
        </p>
        <p class="mt-1 text-xs text-fg-muted">
          Visible variants available to agent procedures.
        </p>
      </div>
      <div class="rounded-md border border-default bg-bg-surface p-3 shadow-xs">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          With guidance
        </p>
        <p class="mt-2 text-sm font-semibold text-fg-strong">
          {{ configuredVoices.length }}
        </p>
        <p class="mt-1 text-xs text-fg-muted">
          Profiles containing markdown voice guidance.
        </p>
      </div>
    </div>

    <UiEmptyState
      v-if="!loading && voices.length === 0"
      title="No voice profiles"
      description="Voice profiles appear here after agent setup."
      size="sm"
    />

    <div
      v-else
      class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,0.75fr)]"
    >
      <DataTable
        :items="voices"
        :columns="columns"
        :loading="loading"
        aria-label="Voice profiles"
        empty-message="No voice profiles yet."
        @row-click="selectVoice"
      >
        <template #cell:is_default="{ row }">
          <UiBadge
            :tone="(row as Voice).is_default ? 'success' : 'neutral'"
            variant="outline"
          >
            {{ (row as Voice).is_default ? 'Default' : 'Variant' }}
          </UiBadge>
        </template>
      </DataTable>

      <aside class="rounded-md border border-default bg-bg-surface p-4 shadow-xs">
        <div
          v-if="selectedVoice"
          class="space-y-4"
        >
          <header class="space-y-2">
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="text-sm font-semibold text-fg-strong">
                {{ selectedVoice.name }}
              </h3>
              <UiBadge
                v-if="selectedVoice.is_default"
                tone="success"
              >
                Default
              </UiBadge>
              <UiBadge tone="neutral">
                v{{ selectedVoice.version }}
              </UiBadge>
            </div>
            <p class="text-xs text-fg-muted">
              Created
              {{ selectedVoice.created_at ? new Date(selectedVoice.created_at).toLocaleString() : '-' }}
            </p>
          </header>

          <div v-if="selectedVoice.voice_md?.trim()">
            <p class="mb-2 text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
              Guidance
            </p>
            <div class="cs-voice-markdown">
              <MarkdownView
                :source="selectedVoice.voice_md"
              />
            </div>
          </div>
          <div
            v-else
            class="rounded-md border border-dashed border-subtle bg-bg-surface-alt p-4 text-sm text-fg-muted"
          >
            No voice guidance has been recorded for this profile.
          </div>
        </div>
        <p
          v-else
          class="text-sm text-fg-muted"
        >
          Select a profile to inspect its guidance.
        </p>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.cs-voice-markdown :deep(.cs-markdown h1) {
  font-size: 1rem;
  line-height: 1.35;
  margin: 0 0 0.5rem;
}

.cs-voice-markdown :deep(.cs-markdown h2) {
  font-size: 0.95rem;
  line-height: 1.35;
  margin: 0.75rem 0 0.35rem;
}

.cs-voice-markdown :deep(.cs-markdown p) {
  margin: 0.35rem 0;
}
</style>
