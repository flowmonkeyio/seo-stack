import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import TrackerWarningSummary from './TrackerWarningSummary.vue'

describe('TrackerWarningSummary', () => {
  it('summarizes graph warnings as advisory signals', () => {
    const wrapper = mount(TrackerWarningSummary, {
      props: {
        warnings: [
          'Task foo has sparse dependency relations.',
          'Workflow step workflow-13-deliver is not ready for closeout while attached child tickets remain open.',
          'Workflow step workflow-13-deliver has verification/docs/signoff/release child tickets that can bypass delivery work.',
        ],
      },
    })

    expect(wrapper.text()).toContain('This task has 3 warnings.')
    expect(wrapper.text()).toContain('3 warnings')
    expect(wrapper.text()).not.toContain('error')
    expect(wrapper.findAll('.tracker-warning-summary__item')).toHaveLength(3)
    expect(wrapper.find('details').attributes('open')).toBeUndefined()
  })

  it('does not render when there are no warnings', () => {
    const wrapper = mount(TrackerWarningSummary, { props: { warnings: [] } })

    expect(wrapper.find('.tracker-warning-summary').exists()).toBe(false)
  })
})
