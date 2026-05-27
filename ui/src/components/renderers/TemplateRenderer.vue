<script setup lang="ts">
import { computed } from 'vue'

import type {
  SchemaLoadedWorkflowTemplate,
  SchemaWorkflowAgentRequirementSpec,
  SchemaWorkflowSkillRequirementSpec,
  SchemaWorkflowTemplateSpec,
} from '@/api'
import { UiBadge, UiJsonBlock, UiPanel, UiSectionHeader } from '@/components/ui'
import { sanitizeForDisplay } from '@/lib/stackos/json'

const props = defineProps<{
  template: SchemaLoadedWorkflowTemplate
}>()

const spec = computed<SchemaWorkflowTemplateSpec>(() => props.template.spec)
const contextRequirements = computed(() => spec.value.context_requirements ?? [])
const agentRequirements = computed(() => spec.value.agent_requirements ?? [])
const skillRequirements = computed(() => spec.value.skill_requirements ?? [])
const inputs = computed(() => spec.value.inputs ?? [])
const outputs = computed(() => spec.value.outputs ?? [])
const approvals = computed(() => spec.value.approval_gates ?? [])
const policies = computed(() => spec.value.policies ?? [])
const hooks = computed(() => spec.value.learning_hooks ?? [])
const rawTemplate = computed(() => sanitizeForDisplay(spec.value))

function requirementTone(
  requirement:
    | SchemaWorkflowAgentRequirementSpec['requirement']
    | SchemaWorkflowSkillRequirementSpec['requirement'],
): 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'accent' {
  if (requirement === 'required') return 'warning'
  if (requirement === 'recommended') return 'info'
  return 'neutral'
}
</script>

<template>
  <div class="space-y-4">
    <UiPanel class="p-4">
      <UiSectionHeader
        :title="spec.name"
        :description="spec.description"
      >
        <template #actions>
          <UiBadge tone="accent">{{ template.summary.source }}</UiBadge>
          <UiBadge v-if="template.summary.plugin_slug">{{ template.summary.plugin_slug }}</UiBadge>
          <UiBadge>{{ spec.version }}</UiBadge>
        </template>
      </UiSectionHeader>

      <dl class="grid gap-3 text-sm md:grid-cols-3">
        <div class="min-w-0">
          <dt class="text-xs text-fg-muted">Key</dt>
          <dd class="truncate font-mono">{{ spec.key }}</dd>
        </div>
        <div class="min-w-0">
          <dt class="text-xs text-fg-muted">Domain</dt>
          <dd class="truncate">{{ spec.domain ?? '-' }}</dd>
        </div>
        <div class="min-w-0">
          <dt class="text-xs text-fg-muted">Origin</dt>
          <dd class="truncate font-mono">{{ template.summary.origin_path ?? '-' }}</dd>
        </div>
      </dl>
    </UiPanel>

    <UiPanel class="p-4">
      <UiSectionHeader
        title="Agents & Skills"
        as="h3"
        description="Generic presets and host skills the caller should adapt before running this workflow."
      >
        <template #actions>
          <UiBadge>{{ agentRequirements.length }} agents</UiBadge>
          <UiBadge>{{ skillRequirements.length }} skills</UiBadge>
        </template>
      </UiSectionHeader>
      <div class="grid gap-4 lg:grid-cols-2">
        <section>
          <h4 class="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-muted">
            Agent Requirements
          </h4>
          <p
            v-if="agentRequirements.length === 0"
            class="text-sm text-fg-muted"
          >
            -
          </p>
          <ul
            v-else
            class="space-y-2"
          >
            <li
              v-for="agent in agentRequirements"
              :key="agent.role"
              class="rounded-md border border-subtle bg-bg-surface px-3 py-2 text-sm"
            >
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-medium text-fg-default">{{ agent.role }}</span>
                <UiBadge :tone="requirementTone(agent.requirement)">
                  {{ agent.requirement }}
                </UiBadge>
              </div>
              <p class="mt-1 truncate font-mono text-xs text-fg-muted">
                {{ agent.agent_preset_ref }}
              </p>
              <p
                v-if="agent.purpose"
                class="mt-2 text-xs text-fg-muted"
              >
                {{ agent.purpose }}
              </p>
              <div
                v-if="agent.applies_to_steps?.length"
                class="mt-2 flex flex-wrap gap-1.5"
              >
                <UiBadge
                  v-for="step in agent.applies_to_steps"
                  :key="step"
                  tone="accent"
                >
                  {{ step }}
                </UiBadge>
              </div>
              <ul
                v-if="agent.handoff_notes?.length"
                class="mt-2 space-y-1 text-xs text-fg-muted"
              >
                <li
                  v-for="note in agent.handoff_notes"
                  :key="note"
                >
                  {{ note }}
                </li>
              </ul>
            </li>
          </ul>
        </section>

        <section>
          <h4 class="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-muted">
            Skill Requirements
          </h4>
          <p
            v-if="skillRequirements.length === 0"
            class="text-sm text-fg-muted"
          >
            -
          </p>
          <ul
            v-else
            class="space-y-2"
          >
            <li
              v-for="skill in skillRequirements"
              :key="skill.skill_ref"
              class="rounded-md border border-subtle bg-bg-surface px-3 py-2 text-sm"
            >
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-mono text-xs font-medium text-fg-default">
                  {{ skill.skill_ref }}
                </span>
                <UiBadge :tone="requirementTone(skill.requirement)">
                  {{ skill.requirement }}
                </UiBadge>
              </div>
              <p
                v-if="skill.purpose"
                class="mt-2 text-xs text-fg-muted"
              >
                {{ skill.purpose }}
              </p>
              <div
                v-if="skill.applies_to_steps?.length"
                class="mt-2 flex flex-wrap gap-1.5"
              >
                <UiBadge
                  v-for="step in skill.applies_to_steps"
                  :key="step"
                  tone="accent"
                >
                  {{ step }}
                </UiBadge>
              </div>
              <ul
                v-if="skill.setup_notes?.length"
                class="mt-2 space-y-1 text-xs text-fg-muted"
              >
                <li
                  v-for="note in skill.setup_notes"
                  :key="note"
                >
                  {{ note }}
                </li>
              </ul>
            </li>
          </ul>
        </section>
      </div>
    </UiPanel>

    <UiPanel class="p-4">
      <UiSectionHeader
        title="Workflow"
        as="h3"
      >
        <template #actions>
          <UiBadge>{{ spec.steps.length }} steps</UiBadge>
        </template>
      </UiSectionHeader>
      <ol class="space-y-2">
        <li
          v-for="(step, index) in spec.steps"
          :key="step.id"
          class="rounded-md border border-subtle bg-bg-surface p-3"
        >
          <div class="mb-1 flex flex-wrap items-center gap-2">
            <span class="font-mono text-xs text-fg-muted">#{{ index + 1 }}</span>
            <span class="font-medium text-fg-default">{{ step.title }}</span>
            <UiBadge>{{ step.id }}</UiBadge>
          </div>
          <p
            v-if="step.purpose"
            class="mb-2 text-sm text-fg-muted"
          >
            {{ step.purpose }}
          </p>
          <div class="grid gap-2 text-xs md:grid-cols-2">
            <div v-if="step.context_refs?.length">
              <span class="font-semibold text-fg-default">Context:</span>
              {{ step.context_refs.join(', ') }}
            </div>
            <div v-if="step.action_refs?.length">
              <span class="font-semibold text-fg-default">Actions:</span>
              {{ step.action_refs.join(', ') }}
            </div>
            <div v-if="step.approval_refs?.length">
              <span class="font-semibold text-fg-default">Approvals:</span>
              {{ step.approval_refs.join(', ') }}
            </div>
            <div v-if="step.output_refs?.length">
              <span class="font-semibold text-fg-default">Outputs:</span>
              {{ step.output_refs.join(', ') }}
            </div>
          </div>
        </li>
      </ol>
    </UiPanel>

    <UiPanel class="p-4">
      <UiSectionHeader
        title="Contracts"
        as="h3"
      />
      <div class="grid gap-4 lg:grid-cols-2">
        <section>
          <h4 class="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-muted">
            Inputs
          </h4>
          <p
            v-if="inputs.length === 0"
            class="text-sm text-fg-muted"
          >
            -
          </p>
          <ul
            v-else
            class="space-y-2"
          >
            <li
              v-for="input in inputs"
              :key="input.key"
              class="flex items-center justify-between gap-3 rounded-md border border-subtle bg-bg-surface px-3 py-2 text-sm"
            >
              <span class="min-w-0 truncate font-medium">{{ input.name ?? input.key }}</span>
              <UiBadge :tone="input.required ? 'warning' : 'neutral'">{{ input.type }}</UiBadge>
            </li>
          </ul>
        </section>
        <section>
          <h4 class="mb-2 text-xs font-semibold uppercase tracking-wide text-fg-muted">
            Outputs
          </h4>
          <p
            v-if="outputs.length === 0"
            class="text-sm text-fg-muted"
          >
            -
          </p>
          <ul
            v-else
            class="space-y-2"
          >
            <li
              v-for="output in outputs"
              :key="output.key"
              class="flex items-center justify-between gap-3 rounded-md border border-subtle bg-bg-surface px-3 py-2 text-sm"
            >
              <span class="min-w-0 truncate font-medium">{{ output.name ?? output.key }}</span>
              <UiBadge>{{ output.type }}</UiBadge>
            </li>
          </ul>
        </section>
      </div>
    </UiPanel>

    <UiPanel class="p-4">
      <UiSectionHeader
        title="Context"
        as="h3"
      >
        <template #actions>
          <UiBadge>{{ contextRequirements.length }}</UiBadge>
        </template>
      </UiSectionHeader>
      <p
        v-if="contextRequirements.length === 0"
        class="text-sm text-fg-muted"
      >
        -
      </p>
      <ul
        v-else
        class="space-y-2"
      >
        <li
          v-for="req in contextRequirements"
          :key="req.id"
          class="rounded-md border border-subtle bg-bg-surface p-3 text-sm"
        >
          <div class="flex flex-wrap items-center gap-2">
            <span class="font-medium">{{ req.id }}</span>
            <UiBadge tone="info">{{ req.source }}</UiBadge>
          </div>
          <p class="mt-1 text-xs text-fg-muted">{{ req.purpose }}</p>
        </li>
      </ul>
    </UiPanel>

    <UiPanel class="p-4">
      <UiSectionHeader
        title="Rules"
        as="h3"
      >
        <template #actions>
          <UiBadge>{{ approvals.length }} approvals</UiBadge>
          <UiBadge>{{ policies.length }} policies</UiBadge>
          <UiBadge>{{ hooks.length }} hooks</UiBadge>
        </template>
      </UiSectionHeader>
      <div class="space-y-2">
        <details class="rounded-md border border-subtle bg-bg-surface">
          <summary class="cursor-pointer px-3 py-2 text-sm font-medium text-fg-default focus-ring">
            Approvals
          </summary>
          <div class="border-t border-subtle p-3">
            <UiJsonBlock
              :data="sanitizeForDisplay(approvals)"
              density="compact"
              max-height="12rem"
              wrap
            />
          </div>
        </details>
        <details class="rounded-md border border-subtle bg-bg-surface">
          <summary class="cursor-pointer px-3 py-2 text-sm font-medium text-fg-default focus-ring">
            Policies
          </summary>
          <div class="border-t border-subtle p-3">
            <UiJsonBlock
              :data="sanitizeForDisplay(policies)"
              density="compact"
              max-height="12rem"
              wrap
            />
          </div>
        </details>
        <details class="rounded-md border border-subtle bg-bg-surface">
          <summary class="cursor-pointer px-3 py-2 text-sm font-medium text-fg-default focus-ring">
            Learning Hooks
          </summary>
          <div class="border-t border-subtle p-3">
            <UiJsonBlock
              :data="sanitizeForDisplay(hooks)"
              density="compact"
              max-height="12rem"
              wrap
            />
          </div>
        </details>
      </div>
    </UiPanel>

    <details class="rounded-md border border-subtle bg-bg-surface">
      <summary class="cursor-pointer px-3 py-2 text-sm font-medium text-fg-default focus-ring">
        Template JSON
      </summary>
      <div class="border-t border-subtle p-3">
        <UiJsonBlock
          :data="rawTemplate"
          density="compact"
          max-height="24rem"
          wrap
        />
      </div>
    </details>
  </div>
</template>
