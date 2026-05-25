<script setup lang="ts">
import { computed, h, ref } from 'vue';
import {
  NCard, NSpace, NButton, NForm, NFormItem, NInput, NSelect, NInputNumber, NAlert, NTag, useMessage,
} from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { apiGet, apiPost, apiDelete, ApiError } from '@/api/client';
import { useApi } from '@/composables/useApi';
import { useCatalogStore } from '@/stores/catalog';
import ResourceTable from '@/components/ResourceTable.vue';
import type { DriveAccountRead, DriveTypeRead } from '@/api/types';

const message = useMessage();
const catalog = useCatalogStore();
void catalog.ensureLoaded();

const { data: drives, loading, error, refresh } = useApi<DriveAccountRead[]>(() => apiGet('/admin/drives'));

const driveTypeOptions = computed(() =>
  catalog.driveTypes.map((dt) => ({ label: dt.label, value: dt.drive_type })),
);

const selectedDriveType = ref<string | null>(null);
const selectedDriveTypeRead = computed<DriveTypeRead | null>(() =>
  catalog.driveTypes.find((d) => d.drive_type === selectedDriveType.value) ?? null,
);

const form = ref<{
  user_id: number | null;
  root_dir: string;
  share_pool_enabled: boolean;
  credentials: Record<string, string>;
}>({ user_id: null, root_dir: '/EmbyCache', share_pool_enabled: false, credentials: {} });

const submitting = ref(false);
const formError = ref<string | null>(null);

function onDriveTypeChange(value: string | null): void {
  selectedDriveType.value = value;
  form.value.credentials = {};
  if (value) {
    const dt = catalog.driveTypes.find((d) => d.drive_type === value);
    if (dt) form.value.root_dir = dt.default_root_dir;
  }
}

async function submit(): Promise<void> {
  if (!selectedDriveType.value) {
    formError.value = '请选择 drive_type';
    return;
  }
  if (form.value.user_id === null) {
    formError.value = '请填写 user_id';
    return;
  }
  const dt = selectedDriveTypeRead.value!;
  const missing = dt.credential_fields.filter((f) => f.required && !form.value.credentials[f.name]?.trim());
  if (missing.length > 0) {
    formError.value = `必填字段缺失: ${missing.map((f) => f.label).join(', ')}`;
    return;
  }

  submitting.value = true;
  formError.value = null;
  try {
    const payload: Record<string, unknown> = {
      user_id: form.value.user_id,
      drive_type: selectedDriveType.value,
      root_dir: form.value.root_dir,
      share_pool_enabled: form.value.share_pool_enabled,
    };
    if (selectedDriveType.value === '115') {
      payload.cookie = form.value.credentials.cookie ?? '';
    } else if (selectedDriveType.value === 'caiyun') {
      payload.caiyun = {
        access_token: form.value.credentials.access_token ?? '',
        refresh_token: form.value.credentials.refresh_token ?? '',
        account_type: form.value.credentials.account_type ?? 'personal_new',
      };
    }
    await apiPost('/admin/drives', payload);
    message.success('Drive 已创建');
    form.value.credentials = {};
    await refresh();
  } catch (caught) {
    formError.value = caught instanceof ApiError ? `${caught.status}: ${JSON.stringify(caught.body)}` : '创建失败';
  } finally {
    submitting.value = false;
  }
}

async function removeDrive(id: number): Promise<void> {
  try {
    await apiDelete(`/admin/drives/${id}`);
    message.success('Drive 已删除');
    await refresh();
  } catch (caught) {
    const msg = caught instanceof ApiError ? `${caught.status}: ${JSON.stringify(caught.body)}` : '删除失败';
    message.error(msg);
  }
}

const columns: DataTableColumns<DriveAccountRead> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: 'User ID', key: 'user_id', width: 90 },
  { title: 'Type', key: 'drive_type', width: 110 },
  { title: 'Root', key: 'root_dir' },
  {
    title: '启用', key: 'enabled', width: 80,
    render: (row) => (row.enabled ? '是' : '否'),
  },
  {
    title: '健康', key: 'health_status', width: 110,
    render: (row) => row.health_status,
  },
  { title: 'Mount', key: 'openlist_mount_path' },
  {
    title: '操作', key: 'actions', width: 100,
    render: (row) =>
      h(
        NButton,
        { size: 'tiny', type: 'error', tertiary: true, onClick: () => removeDrive(row.id) },
        { default: () => '删除' },
      ),
  },
];
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="创建 Drive">
      <NAlert v-if="formError" type="error" :show-icon="false" style="margin-bottom:12px">
        {{ formError }}
      </NAlert>
      <NForm @submit.prevent="submit">
        <NSpace>
          <NFormItem label="User ID" style="min-width:140px">
            <NInputNumber v-model:value="form.user_id" :min="1" />
          </NFormItem>
          <NFormItem label="Drive 类型" style="min-width:200px">
            <NSelect :options="driveTypeOptions" :value="selectedDriveType" @update:value="onDriveTypeChange" />
          </NFormItem>
          <NFormItem label="Root" style="min-width:200px">
            <NInput v-model:value="form.root_dir" />
          </NFormItem>
        </NSpace>
        <NSpace v-if="selectedDriveTypeRead">
          <NFormItem
            v-for="field in selectedDriveTypeRead.credential_fields"
            :key="field.name"
            :label="field.label"
            style="min-width:260px"
          >
            <NInput
              v-model:value="form.credentials[field.name]"
              :type="field.secret ? 'password' : 'text'"
              :show-password-on="field.secret ? 'click' : undefined"
              :placeholder="field.help_text ?? ''"
            />
          </NFormItem>
        </NSpace>
        <NButton type="primary" :loading="submitting" attr-type="submit">创建</NButton>
      </NForm>
    </NCard>

    <NCard title="Drive 列表">
      <ResourceTable
        :columns="columns"
        :rows="drives ?? []"
        :row-key="(r) => r.id"
        :loading="loading"
        :error="error"
        empty-text="尚无 drive"
      />
    </NCard>
  </NSpace>
</template>
