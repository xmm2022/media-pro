import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiGet, apiPost, apiDelete, setUnauthorizedHandler } from '@/api/client';

const originalFetch = globalThis.fetch;

function mockFetchOnce(response: Response): void {
  globalThis.fetch = vi.fn().mockResolvedValueOnce(response);
}

beforeEach(() => {
  setUnauthorizedHandler(null);
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe('apiGet', () => {
  it('appends query params and parses JSON', async () => {
    const fetchSpy = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    globalThis.fetch = fetchSpy;

    const result = await apiGet<{ ok: boolean }>('/admin/media-items', { q: 'Movie', limit: 10 });

    expect(result).toEqual({ ok: true });
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe('/api/admin/media-items?q=Movie&limit=10');
    expect(init.credentials).toBe('include');
  });

  it('omits undefined and null params', async () => {
    const fetchSpy = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({}), { status: 200, headers: { 'content-type': 'application/json' } }),
    );
    globalThis.fetch = fetchSpy;

    await apiGet('/admin/users', { limit: 50, offset: undefined, q: null });

    expect(fetchSpy.mock.calls[0][0]).toBe('/api/admin/users?limit=50');
  });

  it('throws ApiError on non-2xx with parsed body', async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ detail: 'nope' }), {
        status: 400,
        headers: { 'content-type': 'application/json' },
      }),
    );

    await expect(apiGet('/admin/users')).rejects.toMatchObject({
      status: 400,
      body: { detail: 'nope' },
    });

    mockFetchOnce(
      new Response(JSON.stringify({ detail: 'nope' }), {
        status: 400,
        headers: { 'content-type': 'application/json' },
      }),
    );
    await expect(apiGet('/admin/users')).rejects.toBeInstanceOf(ApiError);
  });

  it('invokes the unauthorized handler on 401', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    mockFetchOnce(
      new Response('Unauthorized', { status: 401 }),
    );

    await expect(apiGet('/admin/users')).rejects.toMatchObject({ status: 401 });
    expect(handler).toHaveBeenCalledTimes(1);
  });
});

describe('apiPost and apiDelete', () => {
  it('apiPost sends JSON body', async () => {
    const fetchSpy = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ id: 1 }), { status: 200, headers: { 'content-type': 'application/json' } }),
    );
    globalThis.fetch = fetchSpy;

    const result = await apiPost('/admin/users', { username: 'alice' });

    expect(result).toEqual({ id: 1 });
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe('/api/admin/users');
    expect(init.method).toBe('POST');
    expect(init.headers).toMatchObject({ 'content-type': 'application/json' });
    expect(JSON.parse(init.body as string)).toEqual({ username: 'alice' });
  });

  it('apiDelete sends DELETE', async () => {
    const fetchSpy = vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } }),
    );
    globalThis.fetch = fetchSpy;

    await apiDelete('/admin/drives/1');

    expect(fetchSpy.mock.calls[0][1].method).toBe('DELETE');
  });
});
