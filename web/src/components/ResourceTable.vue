<script setup lang="ts" generic="Row extends Record<string, any> = Record<string, any>">
import { computed } from 'vue';
import { NDataTable, NAlert, NEmpty, NSpin } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';

interface Props {
  columns: DataTableColumns<Row>;
  rows: readonly Row[];
  // Typed as `any` parameter to keep the prop usable from contexts where the
  // generic `Row` cannot be inferred (notably `@vue/test-utils`' `mount()`),
  // while keeping `Row` for `columns`/`rows`.
  rowKey: (row: any) => string | number;
  loading?: boolean;
  error?: Error | null;
  emptyText?: string;
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  error: null,
  emptyText: '没有数据',
});

const showEmpty = computed(() => !props.loading && !props.error && props.rows.length === 0);
</script>

<template>
  <div>
    <NAlert v-if="error" type="error" :show-icon="false" style="margin-bottom:12px">
      {{ error.message }}
    </NAlert>
    <NSpin :show="loading">
      <NEmpty v-if="showEmpty" :description="emptyText" style="padding:24px 0" />
      <NDataTable
        v-else
        :columns="columns"
        :data="[...rows]"
        :row-key="rowKey"
        :bordered="false"
        size="small"
      />
    </NSpin>
  </div>
</template>
