<script setup lang="ts">
import { computed, h, ref } from 'vue';
import { NCard, NSpace, NButton, NInputNumber, NSelect, NTag } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { apiGet } from '@/api/client';
import { useApi } from '@/composables/useApi';
import ResourceTable from '@/components/ResourceTable.vue';
import type { PlaybackRecordRead } from '@/api/types';

const filters = ref<{
  user_id: number | null;
  media_id: number | null;
  route: string | null;
  success: 'true' | 'false' | null;
  limit: number;
  offset: number;
}>({ user_id: null, media_id: null, route: null, success: null, limit: 50, offset: 0 });

const routeOptions = [
  { label: 'self', value: 'self' },
  { label: 'pool', value: 'pool' },
  { label: 'source_copy', value: 'source_copy' },
  { label: 'source_stream', value: 'source_stream' },
];

const successOptions = [
  { label: '成功', value: 'true' },
  { label: '失败', value: 'false' },
];

const queryParams = computed(() => ({
  user_id: filters.value.user_id,
  media_id: filters.value.media_id,
  route: filters.value.route,
  success: filters.value.success === null ? null : filters.value.success === 'true',
  limit: filters.value.limit,
  offset: filters.value.offset,
}));

const { data, loading, error, refresh } = useApi<PlaybackRecordRead[]>(() =>
  apiGet('/admin/playback-records', queryParams.value),
);

const columns: DataTableColumns<PlaybackRecordRead> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: 'User', key: 'user_id', width: 80 },
  { title: 'Media', key: 'media_id', width: 80 },
  { title: 'Route', key: 'route', width: 140 },
  {
    title: '结果', key: 'success', width: 90,
    render: (row) =>
      h(NTag, { type: row.success ? 'success' : 'error', size: 'small', bordered: false }, { default: () => (row.success ? '成功' : '失败') }),
  },
  { title: '延迟 (ms)', key: 'latency_ms', width: 110 },
];
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="筛选">
      <NSpace>
        <NInputNumber v-model:value="filters.user_id" placeholder="user_id" clearable style="width:130px" />
        <NInputNumber v-model:value="filters.media_id" placeholder="media_id" clearable style="width:130px" />
        <NSelect v-model:value="filters.route" :options="routeOptions" placeholder="route" clearable style="width:160px" />
        <NSelect v-model:value="filters.success" :options="successOptions" placeholder="结果" clearable style="width:120px" />
        <NInputNumber v-model:value="filters.limit" :min="1" :max="500" style="width:110px" />
        <NInputNumber v-model:value="filters.offset" :min="0" style="width:110px" />
        <NButton type="primary" :loading="loading" @click="refresh">查询</NButton>
      </NSpace>
    </NCard>

    <NCard title="播放诊断">
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
