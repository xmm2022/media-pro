import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import ResourceTable from '@/components/ResourceTable.vue';

describe('ResourceTable', () => {
  it('renders rows from the rows prop', () => {
    const wrapper = mount(ResourceTable, {
      props: {
        columns: [
          { title: 'ID', key: 'id' },
          { title: 'Name', key: 'name' },
        ],
        rows: [
          { id: 1, name: 'alice' },
          { id: 2, name: 'bob' },
        ],
        rowKey: (r: { id: number }) => r.id,
      },
    });
    expect(wrapper.text()).toContain('alice');
    expect(wrapper.text()).toContain('bob');
  });

  it('shows the empty state when there are no rows and not loading', () => {
    const wrapper = mount(ResourceTable, {
      props: {
        columns: [{ title: 'ID', key: 'id' }],
        rows: [],
        rowKey: (r: { id: number }) => r.id,
        emptyText: '没有记录',
      },
    });
    expect(wrapper.text()).toContain('没有记录');
  });

  it('shows the error state when error is provided', () => {
    const wrapper = mount(ResourceTable, {
      props: {
        columns: [{ title: 'ID', key: 'id' }],
        rows: [],
        rowKey: (r: { id: number }) => r.id,
        error: new Error('boom'),
      },
    });
    expect(wrapper.text()).toContain('boom');
  });
});
