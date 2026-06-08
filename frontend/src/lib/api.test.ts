import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { api, ApiError, request } from './api';

function jsonResponse(body: unknown, init?: { status?: number; ok?: boolean }) {
  const status = init?.status ?? 200;
  const ok = init?.ok ?? (status >= 200 && status < 300);
  return {
    ok,
    status,
    text: () => Promise.resolve(JSON.stringify(body)),
  } as unknown as Response;
}

describe('api fetch client', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('request returns parsed JSON on an ok response', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse({ status: 'ok' }),
    );

    const result = await request<{ status: string }>('/api/health');
    expect(result).toEqual({ status: 'ok' });
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/health', expect.any(Object));
  });

  it('getUncategorizedCount returns a bare number body', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse(42),
    );

    const count = await api.getUncategorizedCount();
    expect(count).toBe(42);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/transactions/uncategorized/count',
      expect.any(Object),
    );
  });

  it('throws ApiError with the right status on a non-ok response', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse({ detail: 'nope' }, { status: 404, ok: false }),
    );

    await expect(api.getBudget()).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      message: 'nope',
    });

    // Confirm it is specifically an ApiError instance.
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse({ detail: 'boom' }, { status: 500, ok: false }),
    );
    let caught: unknown;
    try {
      await api.getBudget();
    } catch (err) {
      caught = err;
    }
    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(500);
    expect((caught as ApiError).body).toEqual({ detail: 'boom' });
  });

  it('getTransactions builds the expected query string', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse([]),
    );

    await api.getTransactions({ uncategorized: true, limit: 10 });

    const url = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toBe('/api/transactions?uncategorized=true&limit=10');
  });

  it('handles an empty (204) body gracefully', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      status: 204,
      text: () => Promise.resolve(''),
    } as unknown as Response);

    const result = await request<undefined>('/api/settings/clear-data', {
      method: 'POST',
    });
    expect(result).toBeUndefined();
  });

  it('does not set Content-Type for FormData bodies', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse({ filename: 'x', accounts: [] }),
    );

    const file = new File(['data'], 'test.csv', { type: 'text/csv' });
    await api.commitImport(file);

    const init = (globalThis.fetch as ReturnType<typeof vi.fn>).mock
      .calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.has('Content-Type')).toBe(false);
    expect(init.body).toBeInstanceOf(FormData);
  });
});
