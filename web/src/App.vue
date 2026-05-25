<script setup lang="ts">
import { computed, h, onMounted } from 'vue';
import { useRoute, useRouter, RouterView } from 'vue-router';
import {
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NMenu,
  NIcon,
  NButton,
  NConfigProvider,
  NMessageProvider,
  NSpace,
} from 'naive-ui';
import { useSessionStore } from '@/stores/session';
import { useCatalogStore } from '@/stores/catalog';

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const catalog = useCatalogStore();

const isLoginRoute = computed(() => route.name === 'login');

const menuOptions = computed(() => {
  const groups: Record<string, { label: string; key: string }[]> = { 运营: [], 数据: [], 诊断: [] };
  for (const r of router.getRoutes()) {
    if (!r.meta?.group || !r.meta?.title) continue;
    groups[r.meta.group as string]?.push({ label: r.meta.title as string, key: r.name as string });
  }
  return (Object.keys(groups) as Array<keyof typeof groups>).flatMap((group) => [
    { type: 'group', label: group, key: `group-${group}`, children: groups[group] },
  ]);
});

const activeKey = computed(() => (route.name as string | undefined) ?? null);

function handleSelect(key: string): void {
  void router.push({ name: key });
}

async function logout(): Promise<void> {
  await session.logout();
  await router.replace({ name: 'login' });
}

onMounted(async () => {
  if (!session.loaded) {
    try {
      await session.refresh();
    } catch {
      /* router guard handles redirect */
    }
  }
  if (!isLoginRoute.value) {
    try {
      await catalog.ensureLoaded();
    } catch {
      /* drive form will surface a retry */
    }
  }
});
</script>

<template>
  <NConfigProvider>
    <NMessageProvider>
      <RouterView v-if="isLoginRoute" />
      <NLayout v-else has-sider style="min-height:100vh">
        <NLayoutSider :width="220" bordered>
          <div style="padding:14px 16px;font-weight:700;font-size:15px">media-pro</div>
          <NMenu :options="menuOptions" :value="activeKey" @update:value="handleSelect" />
        </NLayoutSider>
        <NLayout>
          <NLayoutHeader bordered style="display:flex;align-items:center;justify-content:space-between;padding:0 20px;height:48px">
            <strong>{{ route.meta?.title ?? '管理工作台' }}</strong>
            <NSpace>
              <NButton v-if="session.authEnabled && session.authenticated" size="small" @click="logout">退出</NButton>
            </NSpace>
          </NLayoutHeader>
          <NLayoutContent content-style="padding:20px">
            <RouterView />
          </NLayoutContent>
        </NLayout>
      </NLayout>
    </NMessageProvider>
  </NConfigProvider>
</template>
