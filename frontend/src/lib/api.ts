// Typed fetch client for the BUD backend API.
//
// All endpoints live under the `/api` prefix. The Vite dev server proxies
// `/api` to the FastAPI server, so paths here are RELATIVE and already include
// the `/api` prefix.

import type {
  Account,
  AssignRequest,
  AutoAssignRequest,
  Alert,
  BudgetState,
  BulkCategorizeRequest,
  Category,
  CategoryCreateRequest,
  CategoryUpdateRequest,
  ImportBatch,
  ImportDeleteResult,
  ImportPreview,
  ImportResult,
  MessageResponse,
  MonthlyTrendPoint,
  MoveRequest,
  Rule,
  RuleCreateRequest,
  SettingsSummary,
  SpendingByCategory,
  Target,
  TargetRequest,
  Transaction,
  TransactionCategorizeRequest,
  TransactionQueryParams,
} from './types';

/** Error thrown for non-ok HTTP responses. */
export class ApiError extends Error {
  status: number;
  body?: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

/**
 * Low-level request helper. Parses JSON, throws {@link ApiError} on non-ok.
 * Handles empty/204 bodies and bare (non-object) JSON bodies gracefully.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const isFormData =
    typeof FormData !== 'undefined' && init?.body instanceof FormData;
  // Only set JSON content type for non-FormData bodies.
  if (init?.body !== undefined && !isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(path, { ...init, headers });

  // Parse body (may be empty). Read as text first so we can handle empties and
  // bare JSON values uniformly.
  const text = await response.text();
  let parsed: unknown = undefined;
  if (text.length > 0) {
    try {
      parsed = JSON.parse(text);
    } catch {
      // Non-JSON body — keep raw text.
      parsed = text;
    }
  }

  if (!response.ok) {
    let message = `Request to ${path} failed with status ${response.status}`;
    if (
      parsed &&
      typeof parsed === 'object' &&
      'detail' in parsed &&
      typeof (parsed as { detail: unknown }).detail === 'string'
    ) {
      message = (parsed as { detail: string }).detail;
    } else if (typeof parsed === 'string' && parsed.length > 0) {
      message = parsed;
    }
    throw new ApiError(response.status, message, parsed);
  }

  return parsed as T;
}

function jsonBody(value: unknown): string {
  return JSON.stringify(value);
}

/** Build a query string from optional params, omitting undefined/null. */
function buildQuery(params: Record<string, unknown> | undefined): string {
  if (!params) return '';
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

export const api = {
  // --- Health -------------------------------------------------------------
  getHealth: (): Promise<{ status: string }> =>
    request<{ status: string }>('/api/health'),

  // --- Budget -------------------------------------------------------------
  getBudget: (month?: string): Promise<BudgetState> =>
    request<BudgetState>(`/api/budget${buildQuery({ month })}`),

  assign: (body: AssignRequest): Promise<BudgetState> =>
    request<BudgetState>('/api/budget/assign', {
      method: 'POST',
      body: jsonBody(body),
    }),

  move: (body: MoveRequest): Promise<BudgetState> =>
    request<BudgetState>('/api/budget/move', {
      method: 'POST',
      body: jsonBody(body),
    }),

  autoAssign: (body: AutoAssignRequest): Promise<BudgetState> =>
    request<BudgetState>('/api/budget/auto-assign', {
      method: 'POST',
      body: jsonBody(body),
    }),

  // --- Categories ---------------------------------------------------------
  getCategories: (): Promise<Category[]> =>
    request<Category[]>('/api/categories'),

  createCategory: (body: CategoryCreateRequest): Promise<Category> =>
    request<Category>('/api/categories', {
      method: 'POST',
      body: jsonBody(body),
    }),

  updateCategory: (id: string, body: CategoryUpdateRequest): Promise<Category> =>
    request<Category>(`/api/categories/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: jsonBody(body),
    }),

  setCategoryHidden: (id: string, hidden: boolean): Promise<Category> =>
    request<Category>(`/api/categories/${encodeURIComponent(id)}/hidden`, {
      method: 'PATCH',
      body: jsonBody({ hidden }),
    }),

  deleteCategory: (id: string): Promise<MessageResponse> =>
    request<MessageResponse>(`/api/categories/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    }),

  // --- Category targets ---------------------------------------------------
  setCategoryTarget: (id: string, body: TargetRequest): Promise<Target> =>
    request<Target>(`/api/categories/${encodeURIComponent(id)}/target`, {
      method: 'PUT',
      body: jsonBody(body),
    }),

  deleteCategoryTarget: (id: string): Promise<MessageResponse> =>
    request<MessageResponse>(`/api/categories/${encodeURIComponent(id)}/target`, {
      method: 'DELETE',
    }),

  // --- Accounts -----------------------------------------------------------
  getAccounts: (): Promise<Account[]> => request<Account[]>('/api/accounts'),

  // --- Transactions -------------------------------------------------------
  getTransactions: (params?: TransactionQueryParams): Promise<Transaction[]> =>
    request<Transaction[]>(
      `/api/transactions${buildQuery(params as Record<string, unknown> | undefined)}`,
    ),

  getUncategorized: (limit?: number): Promise<Transaction[]> =>
    request<Transaction[]>(
      `/api/transactions/uncategorized${buildQuery({ limit })}`,
    ),

  getUncategorizedCount: (): Promise<number> =>
    request<number>('/api/transactions/uncategorized/count'),

  categorizeTransaction: (
    id: string,
    body: TransactionCategorizeRequest,
  ): Promise<MessageResponse> =>
    request<MessageResponse>(`/api/transactions/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: jsonBody(body),
    }),

  bulkCategorize: (body: BulkCategorizeRequest): Promise<MessageResponse> =>
    request<MessageResponse>('/api/transactions/bulk-categorize', {
      method: 'POST',
      body: jsonBody(body),
    }),

  // --- Rules --------------------------------------------------------------
  getRules: (): Promise<Rule[]> => request<Rule[]>('/api/rules'),

  createRule: (body: RuleCreateRequest): Promise<Rule> =>
    request<Rule>('/api/rules', {
      method: 'POST',
      body: jsonBody(body),
    }),

  deleteRule: (id: number): Promise<MessageResponse> =>
    request<MessageResponse>(`/api/rules/${id}`, { method: 'DELETE' }),

  applyRule: (id: number): Promise<MessageResponse> =>
    request<MessageResponse>(`/api/rules/${id}/apply`, { method: 'POST' }),

  // --- Alerts -------------------------------------------------------------
  getAlerts: (): Promise<Alert[]> => request<Alert[]>('/api/alerts'),

  runAlerts: (): Promise<MessageResponse> =>
    request<MessageResponse>('/api/alerts/run', { method: 'POST' }),

  dismissAlert: (id: number): Promise<MessageResponse> =>
    request<MessageResponse>(`/api/alerts/${id}/dismiss`, { method: 'POST' }),

  acknowledgeAlert: (id: number): Promise<MessageResponse> =>
    request<MessageResponse>(`/api/alerts/${id}/acknowledge`, {
      method: 'POST',
    }),

  // --- Imports ------------------------------------------------------------
  previewImport: (file: File): Promise<ImportPreview> => {
    const form = new FormData();
    form.append('file', file);
    return request<ImportPreview>('/api/imports/preview', {
      method: 'POST',
      body: form,
    });
  },

  commitImport: (file: File): Promise<ImportResult> => {
    const form = new FormData();
    form.append('file', file);
    return request<ImportResult>('/api/imports', {
      method: 'POST',
      body: form,
    });
  },

  getImportHistory: (): Promise<ImportBatch[]> =>
    request<ImportBatch[]>('/api/imports/history'),

  deleteImport: (id: number): Promise<ImportDeleteResult> =>
    request<ImportDeleteResult>(`/api/imports/${id}`, { method: 'DELETE' }),

  // --- Insights -----------------------------------------------------------
  // Both endpoints take `months` — a trailing-window size in months (ints),
  // NOT a YYYY-MM-01 month string (see backend/routers/insights.py).
  getSpendingByCategory: (months?: number): Promise<SpendingByCategory[]> =>
    request<SpendingByCategory[]>(
      `/api/insights/spending-by-category${buildQuery({ months })}`,
    ),

  getMonthlyTrend: (months?: number): Promise<MonthlyTrendPoint[]> =>
    request<MonthlyTrendPoint[]>(
      `/api/insights/monthly-trend${buildQuery({ months })}`,
    ),

  // --- Settings -----------------------------------------------------------
  getSettingsSummary: (): Promise<SettingsSummary> =>
    request<SettingsSummary>('/api/settings/summary'),

  clearData: (): Promise<MessageResponse> =>
    request<MessageResponse>('/api/settings/clear-data', { method: 'POST' }),
};

// Re-export the low-level helper for advanced callers/tests.
export { request };
