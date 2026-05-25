<script setup lang="ts">
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { NCard, NForm, NFormItem, NInput, NButton, NAlert } from 'naive-ui';
import { useSessionStore } from '@/stores/session';
import { ApiError } from '@/api/client';

const router = useRouter();
const route = useRoute();
const session = useSessionStore();

const password = ref('');
const submitting = ref(false);
const errorMessage = ref<string | null>(null);

async function submit(): Promise<void> {
  if (!password.value) {
    errorMessage.value = '请输入密码';
    return;
  }
  submitting.value = true;
  errorMessage.value = null;
  try {
    await session.login(password.value);
    const next = typeof route.query.next === 'string' ? route.query.next : '/admin/overview';
    await router.replace(next);
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 401) {
      errorMessage.value = '密码错误';
    } else if (caught instanceof ApiError) {
      errorMessage.value = `登录失败 (${caught.status})`;
    } else {
      errorMessage.value = '登录失败';
    }
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div style="display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px">
    <NCard title="media-pro 管理员登录" style="max-width:380px;width:100%">
      <NAlert v-if="errorMessage" type="error" :show-icon="false" style="margin-bottom:16px">
        {{ errorMessage }}
      </NAlert>
      <NForm @submit.prevent="submit">
        <NFormItem label="管理员密码">
          <NInput v-model:value="password" type="password" show-password-on="click" autofocus />
        </NFormItem>
        <NButton type="primary" block :loading="submitting" attr-type="submit">
          登录
        </NButton>
      </NForm>
    </NCard>
  </div>
</template>
