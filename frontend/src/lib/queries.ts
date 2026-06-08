// TanStack Query v5 hooks (queries + mutations) for the BUD backend.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from './api';
import type {
  AssignRequest,
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

// --- Mutations ------------------------------------------------------------

export function useAssign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AssignRequest) => api.assign(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['budget'] });
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
