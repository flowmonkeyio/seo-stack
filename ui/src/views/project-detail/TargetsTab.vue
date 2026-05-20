<script setup lang="ts">
// TargetsTab — read-only publish target readiness.

import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { UiBadge, UiButton, UiCallout, UiEmptyState, UiSectionHeader } from '@/components/ui'
import { apiFetch, formatApiError } from '@/lib/client'
import { useToastsStore } from '@/stores/toasts'
import { PublishTargetKind, type components } from '@/api'

type Target = components['schemas']['PublishTargetOut']
type TargetKind = `${PublishTargetKind}`
type ReadinessTone = 'success' | 'neutral' | 'warning'

interface TargetKindSpec {
  kind: TargetKind
  label: string
  description: string
  usage: string
  hint: string
}

const route = useRoute()
const toasts = useToastsStore()

const projectId = computed<number>(() => Number.parseInt(route.params.id as string, 10))

const targets = ref<Target[]>([])
const loading = ref(false)

const targetKindSpecs: TargetKindSpec[] = [
  {
    kind: 'nuxt-content',
    label: 'Nuxt Content',
    description: 'Writes markdown and assets into a Nuxt Content repository.',
    usage: 'nuxt-content-publish',
    hint: 'Common keys: repo_path, content_subdir, public_subdir, branch.',
  },
  {
    kind: 'wordpress',
    label: 'WordPress',
    description: 'Publishes edited HTML through the WordPress REST API.',
    usage: 'wordpress-publish',
    hint: 'Common keys: wp_url, category_id, status.',
  },
  {
    kind: 'ghost',
    label: 'Ghost',
    description: 'Publishes edited HTML and images through the Ghost Admin API.',
    usage: 'ghost-publish',
    hint: 'Common keys: ghost_url, api_version, tags.',
  },
  {
    kind: 'hugo',
    label: 'Hugo',
    description: 'Writes markdown into a Hugo content repository.',
    usage: 'publish fallback',
    hint: 'Common keys: repo_path, content_subdir, branch.',
  },
  {
    kind: 'astro',
    label: 'Astro',
    description: 'Writes markdown into an Astro content collection.',
    usage: 'publish fallback',
    hint: 'Common keys: repo_path, content_subdir, collection, branch.',
  },
  {
    kind: 'custom-webhook',
    label: 'Custom webhook',
    description: 'Sends a publish payload to a project-owned endpoint.',
    usage: 'custom publish handoff',
    hint: 'Common keys: webhook_url, method, headers.',
  },
]

const procedureSupportedTargetKinds = new Set<TargetKind>(['nuxt-content'])

const activeTargets = computed(() => targets.value.filter((target) => target.is_active))
const primaryTarget = computed(() => targets.value.find((target) => target.is_primary))
const inactiveTargets = computed(() => targets.value.filter((target) => !target.is_active))

async function load(): Promise<void> {
  if (!projectId.value || Number.isNaN(projectId.value)) return
  loading.value = true
  try {
    const res = await apiFetch<Target[]>(`/api/v1/projects/${projectId.value}/publish-targets`)
    targets.value = Array.isArray(res) ? res : []
  } catch (err) {
    toasts.error('Failed to load publish targets', formatApiError(err))
  } finally {
    loading.value = false
  }
}

function specFor(kind: TargetKind): TargetKindSpec {
  return targetKindSpecs.find((spec) => spec.kind === kind) ?? targetKindSpecs[0]
}

function configValue(target: Target, keys: string[]): string | null {
  const config = target.config_json
  if (!config || typeof config !== 'object' || Array.isArray(config)) return null
  for (const key of keys) {
    const value = config[key]
    if (typeof value === 'string' && value.trim()) return value
    if (typeof value === 'number') return String(value)
  }
  return null
}

function configSummary(target: Target): string {
  const kind = target.kind as TargetKind
  if (kind === 'wordpress')
    return configValue(target, ['wp_url', 'site_url', 'base_url']) ?? 'WordPress URL not set'
  if (kind === 'ghost')
    return configValue(target, ['ghost_url', 'site_url', 'base_url']) ?? 'Ghost URL not set'
  if (kind === 'custom-webhook')
    return configValue(target, ['webhook_url', 'url']) ?? 'Webhook URL not set'
  return (
    configValue(target, ['repo_path', 'content_subdir', 'content_dir', 'collection']) ??
    'Repository path not set'
  )
}

function statusLabel(target: Target): string {
  if (target.is_primary && target.is_active) return 'Primary active'
  if (target.is_primary) return 'Primary inactive'
  return target.is_active ? 'Active' : 'Inactive'
}

function statusTone(target: Target): 'success' | 'warning' | 'neutral' {
  if (target.is_primary && target.is_active) return 'success'
  if (target.is_primary && !target.is_active) return 'warning'
  return target.is_active ? 'neutral' : 'warning'
}

function readinessLabel(target: Target): string {
  if (!target.is_active) return 'Inactive'
  if (!procedureSupportedTargetKinds.has(target.kind as TargetKind)) return 'Unsupported by procedure'
  if (!target.is_primary) return 'Available'
  return 'Procedure ready'
}

function readinessTone(target: Target): ReadinessTone {
  if (!target.is_active) return 'neutral'
  if (!procedureSupportedTargetKinds.has(target.kind as TargetKind)) return 'warning'
  return target.is_primary ? 'success' : 'neutral'
}

onMounted(load)
watch(projectId, load)
</script>

<template>
  <section class="space-y-6">
    <UiSectionHeader
      title="Publish targets"
      description="Readiness for destinations that agent publish skills can use."
    >
      <template #actions>
        <UiButton
          size="sm"
          variant="secondary"
          :disabled="loading"
          @click="load"
        >
          {{ loading ? 'Refreshing…' : 'Refresh' }}
        </UiButton>
      </template>
    </UiSectionHeader>

    <UiCallout
      v-if="targets.length > 0 && !primaryTarget"
      tone="warning"
      title="No primary target"
    >
      The agent needs one active primary target before publish procedures can resolve a destination.
    </UiCallout>

    <div class="grid gap-3 md:grid-cols-3">
      <div class="rounded-md border border-default bg-bg-surface p-3 shadow-xs">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          Primary target
        </p>
        <p class="mt-2 text-sm font-semibold text-fg-strong">
          {{ primaryTarget ? specFor(primaryTarget.kind as TargetKind).label : 'Not selected' }}
        </p>
        <p class="mt-1 text-xs text-fg-muted">
          {{
            primaryTarget
              ? configSummary(primaryTarget)
              : 'Publishing procedures need one primary destination.'
          }}
        </p>
      </div>
      <div class="rounded-md border border-default bg-bg-surface p-3 shadow-xs">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          Active targets
        </p>
        <p class="mt-2 text-sm font-semibold text-fg-strong">
          {{ activeTargets.length }} / {{ targets.length }}
        </p>
        <p class="mt-1 text-xs text-fg-muted">
          Active destinations can receive publish handoffs.
        </p>
      </div>
      <div class="rounded-md border border-default bg-bg-surface p-3 shadow-xs">
        <p class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
          Disabled targets
        </p>
        <p class="mt-2 text-sm font-semibold text-fg-strong">
          {{ inactiveTargets.length }}
        </p>
        <p class="mt-1 text-xs text-fg-muted">
          Old destinations remain visible for audit.
        </p>
      </div>
    </div>

    <UiEmptyState
      v-if="!loading && targets.length === 0"
      title="No publish targets"
      description="Publish targets appear here after agent setup."
      size="sm"
    />

    <div
      v-else
      class="grid gap-3"
    >
      <article
        v-for="target in targets"
        :key="target.id"
        class="overflow-hidden rounded-md border bg-bg-surface shadow-xs"
        :class="target.is_primary && target.is_active ? 'border-success-border' : 'border-default'"
      >
        <div class="space-y-4 p-4">
          <header class="space-y-1.5">
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="text-sm font-semibold text-fg-strong">
                {{ specFor(target.kind as TargetKind).label }}
              </h3>
              <UiBadge :tone="statusTone(target)">
                {{ statusLabel(target) }}
              </UiBadge>
              <UiBadge
                v-if="target.is_primary"
                tone="success"
                variant="outline"
              >
                Primary
              </UiBadge>
              <UiBadge
                :tone="readinessTone(target)"
                variant="outline"
              >
                {{ readinessLabel(target) }}
              </UiBadge>
            </div>
            <p class="text-sm text-fg-muted">
              {{ specFor(target.kind as TargetKind).description }}
            </p>
          </header>

          <dl class="grid gap-3 border-t border-subtle pt-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
            <div>
              <dt class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
                Destination
              </dt>
              <dd class="mt-1 text-fg-default">
                {{ configSummary(target) }}
              </dd>
            </div>
            <div>
              <dt class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
                Skill
              </dt>
              <dd class="mt-1 text-fg-default">
                {{ specFor(target.kind as TargetKind).usage }}
              </dd>
            </div>
            <div>
              <dt class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
                Target id
              </dt>
              <dd class="mt-1 text-fg-default">
                #{{ target.id }}
              </dd>
            </div>
            <div>
              <dt class="text-[11px] font-semibold uppercase tracking-wide text-fg-subtle">
                Config keys
              </dt>
              <dd class="mt-1 text-fg-muted">
                {{ specFor(target.kind as TargetKind).hint.replace('Common keys: ', '') }}
              </dd>
            </div>
          </dl>
        </div>
      </article>
    </div>
  </section>
</template>
