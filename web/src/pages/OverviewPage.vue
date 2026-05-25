<script setup lang="ts">
import { NCard, NGrid, NGridItem, NStatistic, NSpace, NButton, NTag, NAlert } from 'naive-ui';
import { apiGet } from '@/api/client';
import { useApi } from '@/composables/useApi';
import type { AdminOverviewRead } from '@/api/types';

const { data, loading, error, refresh } = useApi<AdminOverviewRead>(() => apiGet('/admin/overview'));
</script>

<template>
  <NSpace vertical size="large">
    <NSpace align="center" justify="space-between">
      <p style="margin:0;color:#64748b">查看关键容量、健康状态和播放路由。</p>
      <NButton size="small" :loading="loading" @click="refresh">刷新</NButton>
    </NSpace>

    <NAlert v-if="error" type="error" :show-icon="false">{{ error.message }}</NAlert>

    <NGrid v-if="data" :cols="4" x-gap="12" y-gap="12">
      <NGridItem><NCard><NStatistic label="Drive 总数" :value="data.drives.stats.total" /></NCard></NGridItem>
      <NGridItem><NCard><NStatistic label="Pool 对象" :value="data.pool_objects.stats.total" /></NCard></NGridItem>
      <NGridItem><NCard><NStatistic label="需要关注 (Drive)" :value="data.drives.attention_total" /></NCard></NGridItem>
      <NGridItem><NCard><NStatistic label="需要关注 (Pool)" :value="data.pool_objects.attention_total" /></NCard></NGridItem>
    </NGrid>

    <NCard v-if="data" title="路由分布">
      <NSpace>
        <NTag v-for="(count, route) in data.routes" :key="route" :bordered="false">
          {{ route }}: {{ count }}
        </NTag>
      </NSpace>
    </NCard>
  </NSpace>
</template>
