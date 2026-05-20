import { defineComponent, nextTick, ref } from 'vue'
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import UiDialog from './UiDialog.vue'

const Host = defineComponent({
  components: { UiDialog },
  setup() {
    const parentOpen = ref(false)
    const childOpen = ref(false)
    return { parentOpen, childOpen }
  },
  template: `
    <button id="open-parent" @click="parentOpen = true">Open parent</button>
    <UiDialog v-model="parentOpen" title="Parent dialog">
      <button id="open-child" @click="childOpen = true">Open child</button>
    </UiDialog>
    <UiDialog v-model="childOpen" title="Child dialog" />
  `,
})

function dialogs(): HTMLElement[] {
  return Array.from(document.body.querySelectorAll<HTMLElement>('[role="dialog"]'))
}

describe('UiDialog', () => {
  it('stacks newly opened dialogs above existing dialogs', async () => {
    const w = mount(Host, { attachTo: document.body })

    await w.find('#open-parent').trigger('click')
    await nextTick()
    await w.find('#open-child').trigger('click')
    await nextTick()

    const [parent, child] = dialogs()
    expect(parent.textContent).toContain('Parent dialog')
    expect(child.textContent).toContain('Child dialog')
    expect(Number(child.style.zIndex)).toBeGreaterThan(Number(parent.style.zIndex))

    w.unmount()
  })

  it('lets Escape close only the top dialog in a stack', async () => {
    const w = mount(Host, { attachTo: document.body })

    await w.find('#open-parent').trigger('click')
    await nextTick()
    await w.find('#open-child').trigger('click')
    await nextTick()

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()

    expect(dialogs()).toHaveLength(1)
    expect(dialogs()[0].textContent).toContain('Parent dialog')

    w.unmount()
  })
})
