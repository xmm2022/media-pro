<script setup lang="ts">
import { h, ref } from 'vue';
import {
  NCard, NSpace, NButton, NForm, NFormItem, NInput, NSelect, NAlert, useMessage,
} from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { apiGet, apiPost, ApiError } from '@/api/client';
import { useApi } from '@/composables/useApi';
import ResourceTable from '@/components/ResourceTable.vue';
import type { UserRead } from '@/api/types';

const message = useMessage();

const { data: users, loading, error, refresh } = useApi<UserRead[]>(() => apiGet('/admin/users'));

const form = ref({ username: '', status: 'active' });
const submitting = ref(false);
const formError = ref<string | null>(null);

const statusOptions = [
  { label: 'active', value: 'active' },
  { label: 'disabled', value: 'disabled' },
];

const columns: DataTableColumns<UserRead> = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '用户名', key: 'username' },
  { title: '状态', key: 'status', width: 120 },
];

async function submit(): Promise<void> {
  if (!form.value.username.trim()) {
    formError.value = '用户名必填';
    return;
  }
  submitting.value = true;
  formError.value = null;
  try {
    await apiPost('/admin/users', { username: form.value.username.trim(), status: form.value.status });
    form.value.username = '';
    message.success('用户已创建');
    await refresh();
  } catch (caught) {
    formError.value = caught instanceof ApiError ? `${caught.status}: ${JSON.stringify(caught.body)}` : '创建失败';
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="创建用户">
      <NAlert v-if="formError" type="error" :show-icon="false" style="margin-bottom:12px">
        {{ formError }}
      </NAlert>
      <NForm inline @submit.prevent="submit">
        <NFormItem label="用户名" style="min-width:240px">
          <NInput v-model:value="form.username" placeholder="alice" />
        </NFormItem>
        <NFormItem label="状态" style="min-width:160px">
          <NSelect v-model:value="form.status" :options="statusOptions" />
        </NFormItem>
        <NFormItem label=" ">
          <NButton type="primary" :loading="submitting" attr-type="submit">创建</NButton>
        </NFormItem>
      </NForm>
    </NCard>

    <NCard title="用户列表">
      <ResourceTable
        :columns="columns"
        :rows="users ?? []"
        :row-key="(r) => r.id"
        :loading="loading"
        :error="error"
        empty-text="尚无用户"
      />
    </NCard>
  </NSpace>
</template>
