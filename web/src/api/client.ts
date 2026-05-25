const API_BASE = '/api';

export class ApiError extends Error {
  public readonly status: number;
  public readonly body: unknown;

  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

type UnauthorizedHandler = () => void;

let unauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

function buildUrl(path: string, params?: Record<string, unknown>): string {
  const url = `${API_BASE}${path}`;
  if (!params) {
    return url;
  }
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    search.append(key, String(value));
  }
  const qs = search.toString();
  return qs ? `${url}?${qs}` : url;
}

async function readBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }
  return await response.text();
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  params?: Record<string, unknown>,
): Promise<T> {
  const init: RequestInit = {
    method,
    credentials: 'include',
    headers: body !== undefined ? { 'content-type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  const response = await fetch(buildUrl(path, params), init);

  if (response.status === 401) {
    unauthorizedHandler?.();
  }

  if (!response.ok) {
    const errorBody = await readBody(response);
    throw new ApiError(response.status, errorBody, `${method} ${path} failed with ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await readBody(response)) as T;
}

export function apiGet<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  return request<T>('GET', path, undefined, params);
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>('POST', path, body);
}

export function apiDelete<T = void>(path: string): Promise<T> {
  return request<T>('DELETE', path);
}
