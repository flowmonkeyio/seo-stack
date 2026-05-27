import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import {
  WorkflowAgentRequirementSpecRequirement,
  WorkflowSkillRequirementSpecRequirement,
  type SchemaLoadedWorkflowTemplate,
} from '@/api'
import WorkflowTemplatesView from './WorkflowTemplatesView.vue'

const ORIG_FETCH = globalThis.fetch

describe('WorkflowTemplatesView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    globalThis.fetch = vi.fn(async (input) => {
      const url = String(input)

      if (url === '/api/v1/projects?limit=50') {
        return json({
          items: [
            {
              id: 1,
              slug: 'stackos-local',
              name: 'StackOS Local',
              domain: 'local.stackos',
              locale: 'en-US',
              status: 'active',
              is_active: true,
              settings_json: {},
              created_at: '2026-05-27T00:00:00Z',
              updated_at: '2026-05-27T00:00:00Z',
            },
          ],
          next_cursor: null,
          total_estimate: 1,
        })
      }

      if (url === '/api/v1/projects/1/workflow-templates?plugin_slug=engineering') {
        const loaded = engineeringWorkflow()
        return json({ templates: [loaded.summary], include_shadowed: false })
      }

      if (
        url ===
        '/api/v1/projects/1/workflow-templates/engineering.tracked-delivery?plugin_slug=engineering'
      ) {
        return json(engineeringWorkflow())
      }

      return json({})
    }) as typeof fetch
  })

  afterEach(() => {
    globalThis.fetch = ORIG_FETCH
    vi.restoreAllMocks()
  })

  it('renders the Engineering tracked-delivery workflow with all SDLC agents and skill guidance', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/projects/:id/workflow-templates', component: WorkflowTemplatesView }],
    })
    await router.push('/projects/1/workflow-templates?plugin_slug=engineering')
    await router.isReady()

    const wrapper = mount(WorkflowTemplatesView, { global: { plugins: [router] } })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Engineering Tracked Delivery'))

    expect(wrapper.text()).toContain('engineering.tracked-delivery')
    expect(wrapper.text()).toContain('6 agents')
    expect(wrapper.text()).toContain('1 skills')
    expect(wrapper.text()).toContain('stackos.sdlc.planning')
    expect(wrapper.text()).toContain('stackos.sdlc.architecture')
    expect(wrapper.text()).toContain('stackos.sdlc.adversarial-design-reviewer')
    expect(wrapper.text()).toContain('stackos.sdlc.delivery')
    expect(wrapper.text()).toContain('stackos.sdlc.delivery-reviewer')
    expect(wrapper.text()).toContain('stackos.sdlc.release-ops')
    expect(wrapper.text()).toContain('stackos:stackos')
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/projects/1/workflow-templates?plugin_slug=engineering',
      expect.anything(),
    )
  })
})

function engineeringWorkflow(): SchemaLoadedWorkflowTemplate {
  return {
    summary: {
      key: 'engineering.tracked-delivery',
      name: 'Engineering Tracked Delivery',
      version: '0.1.0',
      description:
        'Reusable SDLC workflow for planning, delivering, reviewing, and releasing engineering changes through StackOS tracker state.',
      domain: 'engineering',
      source: 'plugin',
      precedence: 10,
      plugin_slug: 'engineering',
      project_id: null,
      origin_path: 'plugins/engineering/workflows/tracked-delivery.yaml',
      template_id: null,
      version_id: null,
      shadowed_by: null,
    },
    spec: {
      schema_version: 'stackos.workflow-template.v1',
      key: 'engineering.tracked-delivery',
      name: 'Engineering Tracked Delivery',
      version: '0.1.0',
      description:
        'Reusable SDLC workflow for planning, delivering, reviewing, and releasing engineering changes through StackOS tracker state.',
      domain: 'engineering',
      inputs: [{ key: 'goal', name: 'Goal', type: 'string', required: true, description: '' }],
      outputs: [
        {
          key: 'delivery_summary',
          name: 'Delivery Summary',
          type: 'object',
          required: true,
          description: '',
        },
      ],
      context_requirements: [],
      agent_requirements: [
        agent('planning', 'required', 'stackos.sdlc.planning'),
        agent('architecture', 'recommended', 'stackos.sdlc.architecture'),
        agent(
          'adversarial-design-reviewer',
          'recommended',
          'stackos.sdlc.adversarial-design-reviewer',
        ),
        agent('delivery', 'required', 'stackos.sdlc.delivery'),
        agent('delivery-reviewer', 'required', 'stackos.sdlc.delivery-reviewer'),
        agent('release-ops', 'recommended', 'stackos.sdlc.release-ops'),
      ],
      skill_requirements: [
        {
          skill_ref: 'stackos:stackos',
          requirement: WorkflowSkillRequirementSpecRequirement.recommended,
          purpose: 'Teach the main agent how to operate StackOS MCP and tracker state.',
          applies_to_steps: [],
          setup_notes: ['Adapt generic SDLC presets to the project before creating local agents.'],
        },
      ],
      steps: [
        { id: 'scope-work', title: 'Scope Work', purpose: 'Restate the goal.' },
        { id: 'plan-tickets', title: 'Plan Tracker Tickets', purpose: 'Create tickets.' },
        { id: 'deliver-tickets', title: 'Deliver Tickets', purpose: 'Deliver tickets.' },
      ],
    },
  }
}

function agent(
  role: string,
  requirement: 'required' | 'recommended',
  agent_preset_ref: string,
) {
  return {
    role,
    requirement:
      requirement === 'required'
        ? WorkflowAgentRequirementSpecRequirement.required
        : WorkflowAgentRequirementSpecRequirement.recommended,
    agent_preset_ref,
    purpose: `${role} purpose`,
    applies_to_steps: [],
    handoff_notes: [],
  }
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  })
}
