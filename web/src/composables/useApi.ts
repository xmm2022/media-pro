import { ref, type Ref } from 'vue';
import { ApiError } from '@/api/client';

export interface UseApiOptions {
  immediate?: boolean;
}

export interface UseApiResult<T> {
  data: Ref<T | null>;
  loading: Ref<boolean>;
  error: Ref<ApiError | Error | null>;
  refresh: () => Promise<void>;
}

export function useApi<T>(fetcher: () => Promise<T>, options: UseApiOptions = {}): UseApiResult<T> {
  const { immediate = true } = options;
  const data = ref<T | null>(null) as Ref<T | null>;
  const loading = ref<boolean>(false);
  const error = ref<ApiError | Error | null>(null);

  async function refresh(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      data.value = await fetcher();
    } catch (caught) {
      data.value = null;
      error.value = caught instanceof Error ? caught : new Error(String(caught));
    } finally {
      loading.value = false;
    }
  }

  if (immediate) {
    void refresh();
  }

  return { data, loading, error, refresh };
}
