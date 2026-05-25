<script setup lang="ts">
import { computed, ref } from 'vue';
import { NCard, NSpace, NButton, NInputNumber, NSelect } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { apiGet } from '@/api/client';
import { useApi } from '@/composables/useApi';
import ResourceTable from '@/components/ResourceTable.vue';
import type { PoolObjectRead } from '@/api/types';

const filters = ref<{
  status: string | null;
  media_id: number | null;
  owner_user_id: number | null;
  limit: number;
  offset: number;
}>({ status: null, media_id: null, owner_user_id: null, limit: 50, offset: 0 });

const statusOptions = [
  { label: 'ready', value: 'ready' },
  { label: 'suspect', value: 'suspect' },
  { label: 'cooldown', value: 'cooldown' },
  { label: 'disabled', value: 'disabled' },
  { label: 'stale', value: 'stale' },
];

const queryParams = computed(() => ({
  status: filters.value.status,
  media_id: filters.value.media_id,
  owner_user_id: filters.value.owner_user_id,
  limit: filters.value.limit,
  offset: filters.value.offset,
}));

const { data, loading, error, refresh } = useApi<PoolObjectRead[]>(() =>
  apiGet('/admin/pool-objects', queryParams.value),
);

const columns: DataTableColumns<PoolObjectRead> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: 'Media', key: 'media_id', width: 90 },
  { title: 'Owner', key: 'owner_user_id', width: 90 },
  { title: 'Type', key: 'drive_type', width: 90 },
  { title: 'Path', key: 'target_path' },
  { title: '状态', key: 'status', width: 110 },
  { title: '失败次数', key: 'failure_count', width: 100 },
];
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="筛选">
      <NSpace>
        <NSelect
          v-model:value="filters.status"
          :options="statusOptions"
          placeholder="状态"
          clearable
          style="width:160px"
        />
        <NInputNumber v-model:value="filters.media_id" placeholder="media_id" clearable style="width:140px" />
        <NInputNumber v-model:value="filters.owner_user_id" placeholder="owner_user_id" clearable style="width:160px" />
        <NInputNumber v-model:value="filters.limit" :min="1" :max="500" style="width:120px" />
        <NInputNumber v-model:value="filters.offset" :min="0" style="width:120px" />
        <NButton type="primary" :loading="loading" @click="refresh">查询</NButton>
      </NSpace>
    </NCard>

    <NCard title="Pool 对象">
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
