import { defineStore } from 'pinia';
import { apiGet } from '@/api/client';
import type { DriveTypeRead } from '@/api/types';

interface CatalogState {
  driveTypes: DriveTypeRead[];
  loaded: boolean;
}

export const useCatalogStore = defineStore('catalog', {
  state: (): CatalogState => ({
    driveTypes: [],
    loaded: false,
  }),
  actions: {
    async ensureLoaded(): Promise<void> {
      if (this.loaded) return;
      this.driveTypes = await apiGet<DriveTypeRead[]>('/admin/drive-types');
      this.loaded = true;
    },
  },
});
