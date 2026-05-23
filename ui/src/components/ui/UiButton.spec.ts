import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import UiButton from './UiButton.vue';

describe('UiButton', () => {
  it('renders supported button icons as inline SVGs', () => {
    const wrapper = mount(UiButton, {
      props: { iconLeft: 'plug-zap', iconRight: 'ban' },
      slots: { default: 'Test' },
    });

    expect(wrapper.findAll('svg.ui-button__icon')).toHaveLength(2);
    expect(wrapper.text()).toContain('Test');
  });

  it('does not reserve a fallback icon node for unknown icon names', () => {
    const wrapper = mount(UiButton, {
      props: { iconLeft: 'missing-icon' },
      slots: { default: 'Test' },
    });

    expect(wrapper.find('svg.ui-button__icon').exists()).toBe(false);
  });
});
