// TanStack Query v5 hooks (queries + mutations) for the BUD backend.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from './api';
import type {
  AssignRequest,
  BudgetState,
  BulkCategorizeRequest,
  MoveRequest,
  TransactionCategorizeRequest,
  TransactionQueryParams,
} from './types';

export const queryKeys = {
  budget: (month?: string) => ['budget', month ?? 'current'] as const,
  categories: () => ['categories'] as const,
  accounts: () => ['accounts'] as const,
  transactions: (params?: unknown) => ['transactions', params ?? null] as const,
  uncategorizedCount: () =>
    ['transactions', 'uncategorized', 'count'] as const,
  rules: () => ['rules'] as const,
  alerts: () => ['alerts'] as const,
} as const;

// --- Queries --------------------------------------------------------------

export function useBudget(month?: string) {
  return useQuery({
    queryKey: queryKeys.budget(month),
    queryFn: () => api.getBudget(month),
  });
}

export function useCategories() {
  return useQuery({
    queryKey: queryKeys.categories(),
    queryFn: () => api.getCategories(),
  });
}

export function useAccounts() {
  return useQuery({
    queryKey: queryKeys.accounts(),
    queryFn: () => api.getAccounts(),
  });
}

export function useTransactions(params?: TransactionQueryParams) {
  return useQuery({
    queryKey: queryKeys.transactions(params),
    queryFn: () => api.getTransactions(params),
  });
}

export function useUncategorizedCount() {
  return useQuery({
    queryKey: queryKeys.uncategorizedCount(),
    queryFn: () => api.getUncategorizedCount(),
  });
}

export function useRules() {
  return useQuery({
    queryKey: queryKeys.rules(),
    queryFn: () => api.getRules(),
  });
}

export function useAlerts() {
  return useQuery({
    queryKey: queryKeys.alerts(),
    queryFn: () => api.getAlerts(),
  });
}

// --- Optimistic helpers ---------------------------------------------------

/**
 * Pure transform: given a {@link BudgetState} and the new `assigned` amount for
 * a single category, return a NEW BudgetState reflecting that assignment.
 *
 * All money values are integer milliunits. The accounting is:
 *   delta = newAmount - oldAssigned
 *   category.assigned  := newAmount
 *   category.available += delta   (assigning more puts more in the envelope)
 *   ready_to_assign    -= delta   (assigning reduces money left to assign)
 *   assigned_total     += delta
 *
 * If the category id isn't present, the state is returned unchanged. The input
 * is never mutated — the categories array and the touched category object are
 * cloned.
 */
export function applyOptimisticAssign(
  state: BudgetState,
  categoryId: string,
  newAmount: number,
): BudgetState {
  const index = state.categories.findIndex((c) => c.id === categoryId);
  if (index === -1) return state;

  const target = state.categories[index];
  const delta = newAmount - target.assigned;

  const categories = state.categories.slice();
  categories[index] = {
    ...target,
    assigned: newAmount,
    available: target.available + delta,
  };

  return {
    ...state,
    ready_to_assign: state.ready_to_assign - delta,
    assigned_total: state.assigned_total + delta,
    categories,
  };
}

// --- Mutations ------------------------------------------------------------

export function useAssign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AssignRequest) => api.assign(body),
    onMutate: async (body: AssignRequest) => {
      // Key exactly the way useBudget does: month ?? 'current'.
      const key = queryKeys.budget(body.month ?? undefined);
      await qc.cancelQueries({ queryKey: key });
      const previous = qc.getQueryData<BudgetState>(key);
      if (previous) {
        qc.setQueryData<BudgetState>(
          key,
          applyOptimisticAssign(previous, body.category_id, body.amount),
        );
      }
      return { previous, key };
    },
    onError: (_err, _body, context) => {
      if (context?.previous !== undefined) {
        qc.setQueryData(context.key, context.previous);
      }
    },
    onSettled: (_data, _err, _body, context) => {
      // Reconcile with the server's authoritative numbers.
      if (context?.key) {
        qc.invalidateQueries({ queryKey: context.key });
      } else {
        qc.invalidateQueries({ queryKey: ['budget'] });
      }
    },
  });
}

export function useMove() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MoveRequest) => api.move(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['budget'] });
    },
  });
}

export function useCategorizeTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: TransactionCategorizeRequest;
    }) => api.categorizeTransaction(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] });
      qc.invalidateQueries({ queryKey: queryKeys.uncategorizedCount() });
      qc.invalidateQueries({ queryKey: ['budget'] });
    },
  });
}

export function useBulkCategorize() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: BulkCategorizeRequest) => api.bulkCategorize(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] });
      qc.invalidateQueries({ queryKey: queryKeys.uncategorizedCount() });
      qc.invalidateQueries({ queryKey: ['budget'] });
    },
  });
}
