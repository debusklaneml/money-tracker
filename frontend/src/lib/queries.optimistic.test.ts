import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { api } from './api';
import { applyOptimisticAssign, queryKeys, useAssign } from './queries';
import type { BudgetState } from './types';

function seedState(): BudgetState {
  return {
    month: '2026-06-01',
    ready_to_assign: 200_000,
    income_month: 500_000,
    income_total: 1_000_000,
    assigned_total: 300_000,
    assigned_this_month: 130_000,
    is_past_funded: false,
    categories: [
      {
        id: 'cat-a',
        group: 'Bills',
        name: 'Rent',
        assigned: 100_000,
        activity: -50_000,
        available: 50_000,
        target_amount: null,
        target_cadence: null,
        target_mode: null,
        target_needed: 0,
        underfunded: 0,
        is_payment: false,
      },
      {
        id: 'cat-b',
        group: 'Fun',
        name: 'Dining',
        assigned: 30_000,
        activity: -10_000,
        available: 20_000,
        target_amount: null,
        target_cadence: null,
        target_mode: null,
        target_needed: 0,
        underfunded: 0,
        is_payment: false,
      },
    ],
  };
}

describe('applyOptimisticAssign', () => {
  it('increasing assigned (+50000) shifts ready_to_assign, available, assigned_total', () => {
    const state = seedState();
    const next = applyOptimisticAssign(state, 'cat-a', 150_000);

    const cat = next.categories.find((c) => c.id === 'cat-a')!;
    expect(cat.assigned).toBe(150_000);
    expect(cat.available).toBe(100_000); // 50_000 + 50_000 delta
    expect(next.assigned_total).toBe(350_000); // 300_000 + 50_000
    expect(next.ready_to_assign).toBe(150_000); // 200_000 - 50_000

    // Other category untouched.
    const other = next.categories.find((c) => c.id === 'cat-b')!;
    expect(other).toEqual(seedState().categories[1]);
  });

  it('decreasing assigned (negative delta) moves the numbers the other way', () => {
    const state = seedState();
    const next = applyOptimisticAssign(state, 'cat-a', 70_000); // delta -30_000

    const cat = next.categories.find((c) => c.id === 'cat-a')!;
    expect(cat.assigned).toBe(70_000);
    expect(cat.available).toBe(20_000); // 50_000 - 30_000
    expect(next.assigned_total).toBe(270_000); // 300_000 - 30_000
    expect(next.ready_to_assign).toBe(230_000); // 200_000 + 30_000
  });

  it('unknown category id returns an equivalent state', () => {
    const state = seedState();
    const next = applyOptimisticAssign(state, 'does-not-exist', 999_999);
    expect(next).toEqual(seedState());
  });

  it('does not mutate the input state', () => {
    const state = seedState();
    const snapshot = structuredClone(state);
    const targetRef = state.categories[0];

    const next = applyOptimisticAssign(state, 'cat-a', 150_000);

    // Original deep-equal to its pre-call snapshot.
    expect(state).toEqual(snapshot);
    // Touched category object is a new reference, original object unchanged.
    expect(next.categories[0]).not.toBe(targetRef);
    expect(targetRef.assigned).toBe(100_000);
    expect(targetRef.available).toBe(50_000);
    // Categories array is a new reference.
    expect(next.categories).not.toBe(state.categories);
  });
});

describe('useAssign optimistic cache update', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  function wrapper(client: QueryClient) {
    return ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children);
  }

  it('writes the optimistic budget to the cache before the server responds', async () => {
    const client = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    // Cockpit budget is keyed on the current month (month undefined).
    client.setQueryData(queryKeys.budget(undefined), seedState());

    // api.assign never resolves, so only the optimistic write is observable.
    vi.spyOn(api, 'assign').mockReturnValue(new Promise<BudgetState>(() => {}));

    const { result } = renderHook(() => useAssign(), {
      wrapper: wrapper(client),
    });

    result.current.mutate({ category_id: 'cat-a', amount: 150_000 });

    await waitFor(() => {
      const cached = client.getQueryData<BudgetState>(
        queryKeys.budget(undefined),
      );
      expect(cached?.ready_to_assign).toBe(150_000);
    });

    const cached = client.getQueryData<BudgetState>(queryKeys.budget(undefined));
    const cat = cached!.categories.find((c) => c.id === 'cat-a')!;
    expect(cat.assigned).toBe(150_000);
    expect(cat.available).toBe(100_000);
    expect(cached!.assigned_total).toBe(350_000);

    client.clear();
  });

  it('writes to the explicit-month cache key when month is provided', async () => {
    const client = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    // A budget cached under an explicit month, distinct from the 'current' key.
    client.setQueryData(queryKeys.budget('2026-06-01'), seedState());

    vi.spyOn(api, 'assign').mockReturnValue(new Promise<BudgetState>(() => {}));

    const { result } = renderHook(() => useAssign(), {
      wrapper: wrapper(client),
    });

    result.current.mutate({
      category_id: 'cat-a',
      amount: 150_000,
      month: '2026-06-01',
    });

    await waitFor(() => {
      const cached = client.getQueryData<BudgetState>(
        queryKeys.budget('2026-06-01'),
      );
      expect(cached?.ready_to_assign).toBe(150_000);
    });

    // The 'current' (undefined-month) key must be untouched.
    expect(client.getQueryData(queryKeys.budget(undefined))).toBeUndefined();

    client.clear();
  });

  it('rolls back to the previous state when the server errors', async () => {
    const client = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    client.setQueryData(queryKeys.budget(undefined), seedState());

    vi.spyOn(api, 'assign').mockRejectedValue(new Error('boom'));

    const { result } = renderHook(() => useAssign(), {
      wrapper: wrapper(client),
    });

    result.current.mutate({ category_id: 'cat-a', amount: 150_000 });

    await waitFor(() => expect(result.current.isError).toBe(true));

    const cached = client.getQueryData<BudgetState>(queryKeys.budget(undefined));
    expect(cached?.ready_to_assign).toBe(200_000);
    const cat = cached!.categories.find((c) => c.id === 'cat-a')!;
    expect(cat.assigned).toBe(100_000);

    client.clear();
  });
});
