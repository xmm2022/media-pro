import { defineStore } from 'pinia';
import { apiGet, apiPost } from '@/api/client';
import type { AdminSessionRead } from '@/api/types';

interface SessionState {
  authEnabled: boolean;
  authenticated: boolean;
  loaded: boolean;
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({
    authEnabled: false,
    authenticated: false,
    loaded: false,
  }),
  actions: {
    async refresh(): Promise<void> {
      const session = await apiGet<AdminSessionRead>('/admin/session');
      this.authEnabled = session.auth_enabled;
      this.authenticated = session.authenticated;
      this.loaded = true;
    },
    async login(password: string): Promise<void> {
      await apiPost('/admin/login', { password });
      await this.refresh();
    },
    async logout(): Promise<void> {
      await apiPost('/admin/logout', {});
      this.authenticated = false;
    },
  },
});
