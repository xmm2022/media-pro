<script setup lang="ts">
import { computed, h, ref } from 'vue';
import { NCard, NSpace, NButton, NInputNumber, NSelect, NTag } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { apiGet } from '@/api/client';
import { useApi } from '@/composables/useApi';
import ResourceTable from '@/components/ResourceTable.vue';
import type { TransferJobRead } from '@/api/types';

const filters = ref<{
  status: string | null;
  route_stage: string | null;
  media_id: number | null;
  donor_user_id: number | null;
  target_user_id: number | null;
  limit: number;
  offset: number;
}>({ status: null, route_stage: null, media_id: null, donor_user_id: null, target_user_id: null, limit: 50, offset: 0 });

const statusOptions = [
  { label: 'pending', value: 'pending' },
  { label: 'running', value: 'running' },
  { label: 'succeeded', value: 'succeeded' },
  { label: 'failed', value: 'failed' },
];

const stageOptions = [
  { label: 'try_pool', value: 'try_pool' },
  { label: 'try_source_copy', value: 'try_source_copy' },
];

const queryParams = computed(() => ({
  status: filters.value.status,
  route_stage: filters.value.route_stage,
  media_id: filters.value.media_id,
  donor_user_id: filters.value.donor_user_id,
  target_user_id: filters.value.target_user_id,
  limit: filters.value.limit,
  offset: filters.value.offset,
}));

const { data, loading, error, refresh } = useApi<TransferJobRead[]>(() =>
  apiGet('/admin/transfer-jobs', queryParams.value),
);

function statusColor(status: string): 'success' | 'warning' | 'error' | 'default' {
  if (status === 'succeeded') return 'success';
  if (status === 'failed') return 'error';
  if (status === 'running' || status === 'pending') return 'warning';
  return 'default';
}

const columns: DataTableColumns<TransferJobRead> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: 'Media', key: 'media_id', width: 80 },
  { title: 'Donor', key: 'donor_user_id', width: 90, render: (row) => row.donor_user_id ?? '—' },
  { title: 'Target', key: 'target_user_id', width: 90 },
  { title: 'Stage', key: 'route_stage', width: 160 },
  {
    title: 'Status', key: 'status', width: 120,
    render: (row) => h(NTag, { type: statusColor(row.status), size: 'small', bordered: false }, { default: () => row.status }),
  },
  { title: 'Error', key: 'error_code', render: (row) => row.error_code ?? '—' },
  { title: 'Attempt', key: 'attempt_no', width: 90 },
];
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="筛选">
      <NSpace>
        <NSelect v-model:value="filters.status" :options="statusOptions" placeholder="状态" clearable style="width:140px" />
        <NSelect v-model:value="filters.route_stage" :options="stageOptions" placeholder="route_stage" clearable style="width:180px" />
        <NInputNumber v-model:value="filters.media_id" placeholder="media_id" clearable style="width:130px" />
        <NInputNumber v-model:value="filters.donor_user_id" placeholder="donor_user_id" clearable style="width:160px" />
        <NInputNumber v-model:value="filters.target_user_id" placeholder="target_user_id" clearable style="width:160px" />
        <NInputNumber v-model:value="filters.limit" :min="1" :max="500" style="width:110px" />
        <NInputNumber v-model:value="filters.offset" :min="0" style="width:110px" />
        <NButton type="primary" :loading="loading" @click="refresh">查询</NButton>
      </NSpace>
    </NCard>

    <NCard title="转存历史">
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
