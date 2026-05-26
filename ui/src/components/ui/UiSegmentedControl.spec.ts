import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import UiSegmentedControl from './UiSegmentedControl.vue'

describe('UiSegmentedControl', () => {
  it('renders supported option icons as inline SVGs', () => {
    const wrapper = mount(UiSegmentedControl, {
      props: {
        modelValue: 'graph',
        label: 'View mode',
        options: [
          { key: 'graph', label: 'Graph', icon: 'git-branch' },
          { key: 'tickets', label: 'Tickets', icon: 'list' },
        ],
      },
    })

    expect(wrapper.findAll('svg.ui-segmented-control__icon')).toHaveLength(2)
    expect(wrapper.text()).toContain('Graph')
    expect(wrapper.text()).toContain('Tickets')
  })
})
