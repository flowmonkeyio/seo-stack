<script setup lang="ts">
import { computed, ref } from 'vue'

import type { SchemaActionCallAuditOut, SchemaRunPlanOut } from '@/api'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  UiBadge,
  UiCallout,
  UiCard,
  UiDescriptionList,
  UiIcon,
  UiIconButton,
  UiJsonBlock,
} from '@/components/ui'
import type { DLItem } from '@/components/ui/UiDescriptionList.vue'
import { formatDateTime, sanitizeForDisplay } from '@/lib/stackos/json'

const props = withDefaults(defineProps<{
  plan: SchemaRunPlanOut
  actionCalls?: SchemaActionCallAuditOut[]
}>(), {
  actionCalls: () => [],
})

const expandedStep = ref<string | null>(null)

const issueTone: Record<string, 'danger' | 'warning'> = {
  error: 'danger',
  warning: 'warning',
}

const steps = computed(() => props.plan.steps ?? [])

const planMeta = computed<DLItem[]>(() => [
  { label: 'Run plan', value: `#${props.plan.id}`, mono: true },
  { label: 'Run', value: props.plan.run_id ? `#${props.plan.run_id}` : null },
  { label: 'Template', value: props.plan.template_version },
  { label: 'Source', value: props.plan.template_source },
  { label: 'Started', value: props.plan.started_at ? formatDateTime(props.plan.started_at) : null },
  { label: 'Completed', value: props.plan.completed_at ? formatDateTime(props.plan.completed_at) : null },
])

function callsForStep(stepPk: number): SchemaActionCallAuditOut[] {
  return props.actionCalls.filter((call) => call.run_plan_step_id === stepPk)
}

function toggleStep(stepId: string): void {
  expandedStep.value = expandedStep.value === stepId ? null : stepId
}
</script>

<template>
  <div class="space-y-5">
    <UiCard section>
      <template #header>
        <div class="min-w-0">
          <h3 class="t-h3 text-fg-strong">
            {{ plan.title }}
          </h3>
          <p
            v-if="plan.goal"
            class="mt-0.5 text-sm text-fg-muted"
          >
            {{ plan.goal }}
          </p>
        </div>
        <div class="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
          <StatusBadge
            :status="plan.status"
            kind="run"
          />
          <UiBadge v-if="plan.template_key">
            {{ plan.template_key }}
          </UiBadge>
        </div>
      </template>

      <div class="space-y-4">
        <div
          v-if="(plan.consistency_issues ?? []).length > 0"
          class="space-y-2"
        >
          <UiCallout
            v-for="issue in plan.consistency_issues"
            :key="`${issue.code}-${issue.step_id ?? ''}-${issue.ticket_key ?? ''}`"
            :tone="issueTone[issue.severity] ?? 'warning'"
            density="compact"
          >
            <div class="space-y-1">
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-medium">{{ issue.message }}</span>
                <UiBadge>{{ issue.code }}</UiBadge>
              </div>
              <div class="text-xs text-fg-muted">
                <span v-if="issue.run_id">Run #{{ issue.run_id }}</span>
                <span v-if="issue.step_id"> step {{ issue.step_id }}</span>
                <span v-if="issue.ticket_key"> ticket {{ issue.ticket_key }}</span>
              </div>
            </div>
          </UiCallout>
        </div>

        <UiDescriptionList
          layout="grid"
          :columns="3"
          :items="planMeta"
          aria-label="Run plan metadata"
        />
      </div>
    </UiCard>

    <UiCard section>
      <template #header>
        <h3 class="t-h3 text-fg-strong">
          Steps
        </h3>
        <UiBadge>{{ steps.length }}</UiBadge>
      </template>

      <p
        v-if="steps.length === 0"
        class="text-sm text-fg-muted"
      >
        No steps recorded for this plan.
      </p>
      <ol
        v-else
        class="space-y-2"
      >
        <li
          v-for="step in steps"
          :key="step.id"
          class="rounded-md border border-subtle bg-bg-surface-alt"
        >
          <div class="flex items-center gap-2 px-2.5 py-2">
            <span
              class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-bg-sunken text-2xs font-medium text-fg-muted"
              aria-hidden="true"
            >
              {{ step.position + 1 }}
            </span>
            <span class="min-w-0 truncate text-sm font-medium text-fg-default">
              {{ step.title }}
            </span>
            <StatusBadge
              :status="step.status"
              kind="job"
              :small="true"
            />
            <UiBadge
              v-if="(step.allowed_tools ?? []).length > 0"
              tone="info"
            >
              {{ (step.allowed_tools ?? []).length }} tools
            </UiBadge>
            <span class="ml-auto shrink-0 text-2xs text-fg-subtle">
              {{ formatDateTime(step.started_at) }}
            </span>
            <UiIconButton
              size="sm"
              variant="ghost"
              :aria-label="expandedStep === step.step_id ? `Collapse step ${step.title}` : `Expand step ${step.title}`"
              :aria-expanded="expandedStep === step.step_id"
              :aria-controls="`run-plan-step-${step.id}`"
              @click="toggleStep(step.step_id)"
            >
              <UiIcon
                name="chevron-right"
                :class="[
                  'h-3.5 w-3.5 transition-transform duration-fast',
                  expandedStep === step.step_id && 'rotate-90',
                ]"
                aria-hidden="true"
              />
            </UiIconButton>
          </div>

          <div
            v-if="expandedStep === step.step_id"
            :id="`run-plan-step-${step.id}`"
            class="space-y-3 border-t border-subtle p-3"
          >
            <UiCallout
              v-if="step.error"
              tone="danger"
              density="compact"
            >
              {{ step.error }}
            </UiCallout>
            <p
              v-if="step.purpose"
              class="text-sm text-fg-muted"
            >
              {{ step.purpose }}
            </p>
            <div class="grid gap-3 lg:grid-cols-2">
              <div class="min-w-0">
                <h4 class="mb-1 text-xs font-medium text-fg-muted">
                  Contracts
                </h4>
                <UiJsonBlock
                  :data="sanitizeForDisplay({
                    inputs: step.input_refs_json,
                    context: step.context_refs_json,
                    actions: step.action_refs_json,
                    resources: step.resource_refs_json,
                    approvals: step.approval_refs_json,
                    outputs: step.output_refs_json,
                    tools: step.allowed_tools ?? [],
                  })"
                  density="compact"
                  max-height="14rem"
                  wrap
                />
              </div>
              <div class="min-w-0">
                <h4 class="mb-1 text-xs font-medium text-fg-muted">
                  Result
                </h4>
                <UiJsonBlock
                  :data="sanitizeForDisplay(step.result_json ?? step.expected_outputs_json ?? {})"
                  density="compact"
                  max-height="14rem"
                  wrap
                />
              </div>
            </div>

            <div v-if="callsForStep(step.id).length > 0">
              <h4 class="mb-1 text-xs font-medium text-fg-muted">
                Action calls
              </h4>
              <ul class="space-y-3 border-l border-subtle pl-3">
                <li
                  v-for="call in callsForStep(step.id)"
                  :key="call.id"
                  class="min-w-0 space-y-2"
                >
                  <div class="flex flex-wrap items-center gap-2">
                    <UiBadge tone="accent">
                      {{ call.plugin_slug }}
                    </UiBadge>
                    <span class="font-mono text-2xs text-fg-subtle">{{ call.action_key }}</span>
                    <StatusBadge
                      :status="call.status"
                      kind="job"
                      :small="true"
                    />
                    <span class="text-2xs text-fg-subtle">{{ formatDateTime(call.created_at) }}</span>
                  </div>
                  <UiJsonBlock
                    :data="sanitizeForDisplay({
                      request: call.request_json,
                      response: call.response_json,
                      metadata: call.metadata_json,
                    })"
                    density="compact"
                    max-height="12rem"
                    wrap
                  />
                </li>
              </ul>
            </div>
          </div>
        </li>
      </ol>
    </UiCard>

    <div class="grid gap-5 lg:grid-cols-2">
      <UiCard
        v-if="(plan.approval_requests ?? []).length > 0"
        section
      >
        <template #header>
          <h3 class="t-h3 text-fg-strong">
            Approvals
          </h3>
          <UiBadge>{{ (plan.approval_requests ?? []).length }}</UiBadge>
        </template>
        <UiJsonBlock
          :data="sanitizeForDisplay(plan.approval_requests)"
          density="compact"
          max-height="16rem"
          wrap
        />
      </UiCard>
      <UiCard section>
        <template #header>
          <h3 class="t-h3 text-fg-strong">
            Run context
          </h3>
        </template>
        <UiJsonBlock
          :data="sanitizeForDisplay({
            inputs: plan.inputs_json,
            selected_context: plan.selected_context_json,
            context_filters: plan.context_filters_json,
            grants: plan.grant_snapshot_json,
            budget: plan.budget_snapshot_json,
            policy: plan.policy_snapshot_json,
            outputs: plan.output_contract_json,
            metadata: plan.metadata_json,
          })"
          density="compact"
          max-height="16rem"
          wrap
        />
      </UiCard>
    </div>
  </div>
</template>
