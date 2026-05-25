import { describe, expect, it, vi } from 'vitest';
import { nextTick } from 'vue';
import { useApi } from '@/composables/useApi';
import { ApiError } from '@/api/client';

async function flush(): Promise<void> {
  await nextTick();
  await new Promise<void>((resolve) => setTimeout(resolve, 0));
  await nextTick();
}

describe('useApi', () => {
  it('starts with loading=true and resolves with data', async () => {
    const fetcher = vi.fn().mockResolvedValue(['item']);
    const { data, loading, error } = useApi(fetcher);

    expect(loading.value).toBe(true);
    expect(data.value).toBeNull();

    await flush();

    expect(loading.value).toBe(false);
    expect(error.value).toBeNull();
    expect(data.value).toEqual(['item']);
  });

  it('captures errors and clears data', async () => {
    const fetcher = vi.fn().mockRejectedValue(new ApiError(500, { detail: 'boom' }, 'boom'));
    const { data, loading, error } = useApi(fetcher);

    await flush();

    expect(loading.value).toBe(false);
    expect(data.value).toBeNull();
    expect(error.value).toBeInstanceOf(ApiError);
    expect((error.value as ApiError).status).toBe(500);
  });

  it('refresh re-invokes the fetcher and resets state', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce([1]).mockResolvedValueOnce([2]);
    const { data, refresh } = useApi(fetcher);

    await flush();
    expect(data.value).toEqual([1]);

    const refreshPromise = refresh();
    await flush();
    await refreshPromise;

    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(data.value).toEqual([2]);
  });

  it('skips initial fetch when immediate=false', async () => {
    const fetcher = vi.fn().mockResolvedValue('x');
    const { data, loading, refresh } = useApi(fetcher, { immediate: false });

    expect(loading.value).toBe(false);
    expect(fetcher).not.toHaveBeenCalled();

    await refresh();

    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(data.value).toBe('x');
  });
});
