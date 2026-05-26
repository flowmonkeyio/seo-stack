import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { h } from 'vue'

import UiDropdownMenu from './UiDropdownMenu.vue'

describe('UiDropdownMenu', () => {
  it('renders supported item icons as inline SVGs', async () => {
    const wrapper = mount(UiDropdownMenu, {
      props: {
        items: [{ key: 'edit', label: 'Edit', icon: 'settings' }],
      },
      slots: {
        trigger: ({ toggle }: { toggle: () => void }) =>
          h('button', { 'data-dropdown-trigger': '', type: 'button', onClick: toggle }, 'Open'),
      },
    })

    await wrapper.find('[data-dropdown-trigger]').trigger('click')

    expect(wrapper.find('svg.ui-dropdown__icon').exists()).toBe(true)
  })
})
