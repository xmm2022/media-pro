import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';
import LoginPage from '@/pages/LoginPage.vue';
import OverviewPage from '@/pages/OverviewPage.vue';
import UsersPage from '@/pages/UsersPage.vue';
import DrivesPage from '@/pages/DrivesPage.vue';
import PoolPage from '@/pages/PoolPage.vue';
import MediaItemsPage from '@/pages/MediaItemsPage.vue';
import TransferJobsPage from '@/pages/TransferJobsPage.vue';
import PlaybackRecordsPage from '@/pages/PlaybackRecordsPage.vue';
import { useSessionStore } from '@/stores/session';
import { setUnauthorizedHandler } from '@/api/client';

const routes: RouteRecordRaw[] = [
  { path: '/admin', redirect: '/admin/overview' },
  { path: '/admin/login', name: 'login', component: LoginPage, meta: { public: true } },
  { path: '/admin/overview', name: 'overview', component: OverviewPage, meta: { title: '系统概览', group: '运营' } },
  { path: '/admin/users', name: 'users', component: UsersPage, meta: { title: '用户管理', group: '运营' } },
  { path: '/admin/drives', name: 'drives', component: DrivesPage, meta: { title: 'Drive 管理', group: '运营' } },
  { path: '/admin/pool', name: 'pool', component: PoolPage, meta: { title: 'Pool 对象', group: '运营' } },
  { path: '/admin/media-items', name: 'media-items', component: MediaItemsPage, meta: { title: '媒体清单', group: '数据' } },
  { path: '/admin/transfer-jobs', name: 'transfer-jobs', component: TransferJobsPage, meta: { title: '转存历史', group: '诊断' } },
  { path: '/admin/playback-records', name: 'playback-records', component: PlaybackRecordsPage, meta: { title: '播放诊断', group: '诊断' } },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  if (to.meta.public) return true;
  const session = useSessionStore();
  if (!session.loaded) {
    try {
      await session.refresh();
    } catch {
      return { name: 'login', query: { next: to.fullPath } };
    }
  }
  if (!session.authEnabled) return true;
  if (session.authenticated) return true;
  return { name: 'login', query: { next: to.fullPath } };
});

export function installUnauthorizedRedirect(): void {
  setUnauthorizedHandler(() => {
    const current = router.currentRoute.value;
    if (current.name === 'login') return;
    void router.replace({ name: 'login', query: { next: current.fullPath } });
  });
}
