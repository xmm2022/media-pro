<script setup lang="ts">
import { computed, ref } from 'vue';
import { NCard, NSpace, NButton, NInput, NInputNumber } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { apiGet } from '@/api/client';
import { useApi } from '@/composables/useApi';
import ResourceTable from '@/components/ResourceTable.vue';
import type { MediaItemRead } from '@/api/types';

const filters = ref({ q: '', fingerprint: '', limit: 50, offset: 0 });

const queryParams = computed(() => ({
  q: filters.value.q.trim() || null,
  fingerprint: filters.value.fingerprint.trim() || null,
  limit: filters.value.limit,
  offset: filters.value.offset,
}));

const { data, loading, error, refresh } = useApi<MediaItemRead[]>(() =>
  apiGet('/admin/media-items', queryParams.value),
);

const columns: DataTableColumns<MediaItemRead> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: 'Source Path', key: 'source_path' },
  { title: 'Fingerprint', key: 'fingerprint', width: 200 },
  { title: 'Size', key: 'size', width: 110 },
  { title: 'MTime', key: 'mtime', width: 180, render: (row) => row.mtime ?? '—' },
  { title: 'OpenList', key: 'openlist_path' },
];
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="筛选">
      <NSpace>
        <NInput v-model:value="filters.q" placeholder="路径关键字" style="width:240px" />
        <NInput v-model:value="filters.fingerprint" placeholder="fingerprint" style="width:220px" />
        <NInputNumber v-model:value="filters.limit" :min="1" :max="500" style="width:120px" />
        <NInputNumber v-model:value="filters.offset" :min="0" style="width:120px" />
        <NButton type="primary" :loading="loading" @click="refresh">查询</NButton>
      </NSpace>
    </NCard>

    <NCard title="媒体清单">
      <ResourceTable
        :columns="columns"
        :rows="data ?? []"
        :row-key="(r) => r.id"
        :loading="loading"
        :error="error"
        empty-text="无匹配记录"
      />
    </NCard>
  </NSpace>
</template>
