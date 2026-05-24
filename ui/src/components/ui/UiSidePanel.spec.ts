import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import UiSidePanel from './UiSidePanel.vue';

describe('UiSidePanel', () => {
  it('scrolls the body by default', () => {
    const wrapper = mount(UiSidePanel, {
      props: { modelValue: true, title: 'Panel' },
      slots: { default: '<div style="height: 1200px">Long content</div>' },
      attachTo: document.body,
    });

    expect(wrapper.find('.ui-sidepanel__body').classes()).toContain('overflow-y-auto');

    wrapper.unmount();
  });

  it('allows body scrolling to be disabled explicitly', () => {
    const wrapper = mount(UiSidePanel, {
      props: { modelValue: true, title: 'Panel', scrollBody: false },
      attachTo: document.body,
    });

    expect(wrapper.find('.ui-sidepanel__body').classes()).not.toContain('overflow-y-auto');

    wrapper.unmount();
  });
});
