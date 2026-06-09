// TypeScript types mirroring the backend Pydantic schemas.
//
// IMPORTANT: all money fields are integers in milliunits ($1.00 == 1000) and
// are represented as plain `number`. Months are `YYYY-MM-01` strings; dates are
// `YYYY-MM-DD` strings.

// --- Budget ---------------------------------------------------------------

export interface CategoryState {
  id: string;
  group: string;
  name: string;
  assigned: number;
  activity: number;
  available: number;
  target_amount: number | null;
  target_cadence: string | null;
  target_mode: string | null;
  target_needed: number;
  underfunded: number;
  is_payment: boolean;
}

export interface BudgetState {
  month: string;
  ready_to_assign: number;
  income_month: number;
  income_total: number;
  assigned_total: number;
  categories: CategoryState[];
}

// --- Categories -----------------------------------------------------------

export interface Category {
  id: string;
  category_group_id: string | null;
  category_group_name: string | null;
  name: string;
  hidden: boolean;
  budgeted: number;
  activity: number;
  balance: number;
  goal_type: string | null;
  goal_target: number | null;
  goal_target_month: string | null;
  sort_order: number;
}

// --- Accounts -------------------------------------------------------------

export interface Account {
  id: string;
  name: string;
  type: string | null;
  on_budget: boolean;
  closed: boolean;
  balance: number;
  cleared_balance: number;
  uncleared_balance: number;
  account_number: string | null;
}

// --- Transactions ---------------------------------------------------------

export interface Transaction {
  id: string;
  account_id: string | null;
  account_name: string | null;
  date: string;
  amount: number;
  memo: string | null;
  cleared: string | null;
  approved: boolean;
  flag_color: string | null;
  payee_id: string | null;
  payee_name: string | null;
  category_id: string | null;
  category_name: string | null;
  transfer_account_id: string | null;
  transfer_transaction_id: string | null;
  import_id: string | null;
  deleted: boolean;
}

// --- Rules ----------------------------------------------------------------

/** Which transaction field a rule matches against. */
export type RuleMatchField = 'payee' | 'memo';
/** How a rule's pattern is compared to the field. */
export type RuleMatchType = 'contains' | 'equals' | 'regex';

export interface Rule {
  id: number;
  match_field: RuleMatchField;
  match_type: RuleMatchType;
  pattern: string;
  category_id: string;
  category_name: string | null;
  group_name: string | null;
  priority: number;
}

// --- Alerts ---------------------------------------------------------------

export interface Alert {
  id: number | null;
  alert_type: string;
  severity: string;
  title: string;
  description: string | null;
  related_entity_id: string | null;
  related_entity_type: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
  acknowledged_at: string | null;
  dismissed: boolean;
}

// --- Imports --------------------------------------------------------------

export interface ImportResult {
  filename: string;
  accounts: string[];
  imported: number;
  duplicates: number;
  auto_categorized: number;
  ai_categorized: number;
  already_imported_file: boolean;
  date_min: string | null;
  date_max: string | null;
}

export interface ImportPreview {
  filename: string;
  accounts: string[];
  new_transactions: Transaction[];
  duplicate_count: number;
  already_imported_file: boolean;
  date_min: string | null;
  date_max: string | null;
}

export interface ImportBatch {
  id: number;
  account_id: string | null;
  filename: string | null;
  file_hash: string | null;
  imported_at: string | null;
  txn_count: number;
  duplicate_count: number;
  date_min: string | null;
  date_max: string | null;
}

export interface ImportDeleteResult {
  id: number;
  deleted_transactions: number;
}

// --- Insights -------------------------------------------------------------
// Field names mirror backend/routers/insights.py exactly.

export interface SpendingByCategory {
  category_id: string | null;
  category_name: string | null;
  total_amount: number;
  transaction_count: number;
}

export interface MonthlyTrendPoint {
  month: string;
  total_amount: number;
}

// --- Settings -------------------------------------------------------------
// Field names mirror backend/routers/settings.py exactly.

export interface SettingsSummary {
  account_count: number;
  category_count: number;
  transaction_count: number;
  uncategorized_count: number;
  rule_count: number;
  active_alert_count: number;
  current_month: string;
  ready_to_assign: number;
  db_path: string;
}

// --- Generic --------------------------------------------------------------

export interface MessageResponse {
  status: string;
  message: string | null;
}

// --- Request bodies -------------------------------------------------------

export interface AssignRequest {
  category_id: string;
  amount: number;
  month?: string | null;
}

export interface MoveRequest {
  from_id: string;
  to_id: string;
  amount: number;
  month?: string | null;
}

export type AutoAssignStrategy =
  | 'underfunded'
  | 'assigned_last_month'
  | 'average_assigned'
  | 'average_spent';

export interface AutoAssignRequest {
  strategy: AutoAssignStrategy;
  month?: string | null;
  lookback?: number;
}

export interface CategoryCreateRequest {
  group: string;
  name: string;
}

export interface TargetRequest {
  amount_milliunits: number;
  cadence: string;
  mode: string;
  every_n_months?: number;
  day_of_month?: number | null;
  month_of_year?: number | null;
}

export interface Target extends TargetRequest {
  category_id: string;
}

export interface CategoryUpdateRequest {
  name: string;
  group: string;
}

export interface TransactionCategorizeRequest {
  category_id?: string | null;
  category_name?: string | null;
}

export interface BulkCategorizeRequest {
  transaction_ids: string[];
  category_id?: string | null;
  category_name?: string | null;
}

export interface RuleCreateRequest {
  pattern: string;
  category_id: string;
  match_field?: RuleMatchField;
  match_type?: RuleMatchType;
  priority?: number;
}

// --- Query params ---------------------------------------------------------

export interface TransactionQueryParams {
  category_id?: string;
  account_id?: string;
  search?: string;
  uncategorized?: boolean;
  limit?: number;
  offset?: number;
}
