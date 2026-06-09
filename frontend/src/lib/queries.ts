// TanStack Query v5 hooks (queries + mutations) for the BUD backend.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from './api';
import type {
  AssignRequest,
  AutoAssignRequest,
  BudgetState,
  BulkCategorizeRequest,
  CategoryCreateRequest,
  CategoryUpdateRequest,
  MoveRequest,
  RuleCreateRequest,
  TargetRequest,
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
  importHistory: () => ['imports', 'history'] as const,
  spendingByCategory: (months?: number) =>
    ['insights', 'spending', months ?? 'default'] as const,
  monthlyTrend: (months?: number) =>
    ['insights', 'trend', months ?? 'default'] as const,
  settingsSummary: () => ['settings', 'summary'] as const,
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

export function useTransactions(
  params?: TransactionQueryParams,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: queryKeys.transactions(params),
    queryFn: () => api.getTransactions(params),
    // Defaults to enabled; callers can gate the fetch (e.g. wait for a
    // selection) without firing an unfiltered fetch-all on mount.
    enabled: options?.enabled,
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

export function useImportHistory() {
  return useQuery({
    queryKey: queryKeys.importHistory(),
    queryFn: () => api.getImportHistory(),
  });
}

export function useSpendingByCategory(months?: number) {
  return useQuery({
    queryKey: queryKeys.spendingByCategory(months),
    queryFn: () => api.getSpendingByCategory(months),
  });
}

export function useMonthlyTrend(months?: number) {
  return useQuery({
    queryKey: queryKeys.monthlyTrend(months),
    queryFn: () => api.getMonthlyTrend(months),
  });
}

export function useSettingsSummary() {
  return useQuery({
    queryKey: queryKeys.settingsSummary(),
    queryFn: () => api.getSettingsSummary(),
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
 *   ready_to_assign     -= delta   (assigning reduces money left to assign)
 *   assigned_total      += delta   (the global cash pool)
 *   assigned_this_month += delta   (this month's figure; the query is per-month)
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
    assigned_this_month: state.assigned_this_month + delta,
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

export function useAutoAssign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AutoAssignRequest) => api.autoAssign(body),
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

// --- Category management mutations ----------------------------------------

export function useCreateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CategoryCreateRequest) => api.createCategory(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.categories() });
      qc.invalidateQueries({ queryKey: ['budget'] });
    },
  });
}

export function useUpdateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: CategoryUpdateRequest }) =>
      api.updateCategory(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.categories() });
      qc.invalidateQueries({ queryKey: ['budget'] });
    },
  });
}

export function useSetCategoryHidden() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, hidden }: { id: string; hidden: boolean }) =>
      api.setCategoryHidden(id, hidden),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.categories() });
      qc.invalidateQueries({ queryKey: ['budget'] });
    },
  });
}

export function useDeleteCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteCategory(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.categories() });
      qc.invalidateQueries({ queryKey: ['budget'] });
    },
  });
}

// --- Category target mutations --------------------------------------------

export function useSetCategoryTarget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: TargetRequest }) =>
      api.setCategoryTarget(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.categories() });
      qc.invalidateQueries({ queryKey: ['budget'] });
    },
  });
}

export function useDeleteCategoryTarget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteCategoryTarget(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.categories() });
      qc.invalidateQueries({ queryKey: ['budget'] });
    },
  });
}

// --- Import mutations ------------------------------------------------------

export function usePreviewImport() {
  return useMutation({
    mutationFn: (file: File) => api.previewImport(file),
  });
}

export function useCommitImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.commitImport(file),
    onSuccess: () => {
      // A commit changes transactions, the budget, and import history.
      qc.invalidateQueries({ queryKey: ['transactions'] });
      qc.invalidateQueries({ queryKey: queryKeys.uncategorizedCount() });
      qc.invalidateQueries({ queryKey: ['budget'] });
      qc.invalidateQueries({ queryKey: queryKeys.importHistory() });
    },
  });
}

export function useDeleteImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteImport(id),
    onSuccess: () => {
      // Deleting an upload removes its transactions, which shifts the budget
      // and uncategorized count, and updates import history.
      qc.invalidateQueries({ queryKey: ['transactions'] });
      qc.invalidateQueries({ queryKey: queryKeys.uncategorizedCount() });
      qc.invalidateQueries({ queryKey: ['budget'] });
      qc.invalidateQueries({ queryKey: queryKeys.importHistory() });
    },
  });
}

// --- Rule mutations --------------------------------------------------------

export function useCreateRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RuleCreateRequest) => api.createRule(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.rules() });
    },
  });
}

export function useDeleteRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteRule(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.rules() });
    },
  });
}

export function useApplyRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.applyRule(id),
    onSuccess: () => {
      // Applying a rule re-categorizes already-imported transactions, which
      // also shifts category activity in the budget. The ['transactions']
      // prefix also covers the uncategorized-count key.
      qc.invalidateQueries({ queryKey: ['transactions'] });
      qc.invalidateQueries({ queryKey: ['budget'] });
    },
  });
}

// --- Alert mutations -------------------------------------------------------

export function useRunAlerts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.runAlerts(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.alerts() });
      qc.invalidateQueries({ queryKey: queryKeys.settingsSummary() });
    },
  });
}

export function useDismissAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.dismissAlert(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.alerts() });
      qc.invalidateQueries({ queryKey: queryKeys.settingsSummary() });
    },
  });
}

export function useAcknowledgeAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.acknowledgeAlert(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.alerts() });
    },
  });
}
