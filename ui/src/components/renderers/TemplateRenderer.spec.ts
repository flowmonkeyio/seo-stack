import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import {
  WorkflowAgentRequirementSpecRequirement,
  WorkflowSkillRequirementSpecRequirement,
  type SchemaLoadedWorkflowTemplate,
} from '@/api'
import TemplateRenderer from './TemplateRenderer.vue'

describe('TemplateRenderer', () => {
  it('renders reusable workflow structure and not action payloads', () => {
    const template: SchemaLoadedWorkflowTemplate = {
      summary: {
        key: 'core.review',
        name: 'Review',
        version: '0.1.0',
        description: 'Review context.',
        domain: 'core',
        source: 'plugin',
        precedence: 10,
        plugin_slug: 'core',
        project_id: null,
        origin_path: 'plugins/core/workflows/review.yaml',
        template_id: null,
        version_id: null,
        shadowed_by: null,
      },
      spec: {
        schema_version: 'stackos.workflow-template.v1',
        key: 'core.review',
        name: 'Review',
        version: '0.1.0',
        description: 'Review context.',
        domain: 'core',
        inputs: [{ key: 'goal', name: 'Goal', type: 'string', required: true, description: '' }],
        outputs: [{ key: 'plan', name: 'Plan', type: 'object', required: true, description: '' }],
        context_requirements: [
          {
            id: 'recent_runs',
            source: 'runs',
            purpose: 'Read bounded run context.',
            fields: ['kind', 'status'],
            max_items: 10,
            return_mode: 'compact',
          },
        ],
        agent_requirements: [
          {
            role: 'planning',
            requirement: WorkflowAgentRequirementSpecRequirement.required,
            agent_preset_ref: 'stackos.sdlc.planning',
            purpose: 'Plan tickets and dependencies.',
            applies_to_steps: ['review'],
            handoff_notes: ['Use tracker tickets for sequencing.'],
          },
        ],
        skill_requirements: [
          {
            skill_ref: 'stackos:stackos',
            requirement: WorkflowSkillRequirementSpecRequirement.recommended,
            purpose: 'Use StackOS MCP, tracker, run plans, and evidence conventions.',
            applies_to_steps: ['review'],
            setup_notes: ['Load the StackOS skill before workflow execution when supported.'],
          },
        ],
        steps: [
          {
            id: 'review',
            title: 'Review',
            purpose: 'Review bounded context.',
            context_refs: ['recent_runs'],
            output_refs: ['plan'],
          },
        ],
      },
    }

    const w = mount(TemplateRenderer, { props: { template } })

    expect(w.text()).toContain('Review')
    expect(w.text()).toContain('recent_runs')
    expect(w.text()).toContain('Agents & Skills')
    expect(w.text()).toContain('stackos.sdlc.planning')
    expect(w.text()).toContain('stackos:stackos')
    expect(w.text()).toContain('Workflow')
    expect(w.text()).not.toContain('credential_ref')
  })
})
