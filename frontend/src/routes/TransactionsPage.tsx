// TransactionsPage — list transactions with search/account/uncategorized
// filtering, multi-row selection, and a bulk categorize action. Single-row
// categorization is available via the per-row category select.

import { useEffect, useMemo, useState } from 'react'

import {
  useBulkCategorize,
  useCategories,
  useCategorizeTransaction,
  useTransactions,
} from '../lib/queries'
import type { Transaction, TransactionQueryParams } from '../lib/types'
import TransactionFilters, {
  type Filters,
} from '../components/transactions/TransactionFilters'
import TransactionTable from '../components/transactions/TransactionTable'
import BulkCategorizeBar from '../components/transactions/BulkCategorizeBar'

const EMPTY_FILTERS: Filters = {
  search: '',
  account_id: undefined,
  uncategorized: false,
}

/** Build the query params the API understands from the UI filter state. */
function toQueryParams(filters: Filters): TransactionQueryParams {
  const params: TransactionQueryParams = {}
  if (filters.search.trim() !== '') params.search = filters.search.trim()
  if (filters.account_id) params.account_id = filters.account_id
  if (filters.uncategorized) params.uncategorized = true
  return params
}

/** Unique account options derived from the loaded transactions. */
function deriveAccounts(
  transactions: Transaction[],
): { id: string; name: string }[] {
  const seen = new Map<string, string>()
  for (const txn of transactions) {
    if (txn.account_id && !seen.has(txn.account_id)) {
      seen.set(txn.account_id, txn.account_name ?? txn.account_id)
    }
  }
  return [...seen.entries()].map(([id, name]) => ({ id, name }))
}

export default function TransactionsPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const params = useMemo(() => toQueryParams(filters), [filters])

  const {
    data: transactions,
    isLoading,
    isError,
  } = useTransactions(params)
  const { data: categories } = useCategories()
  const bulkCategorize = useBulkCategorize()
  const categorizeRow = useCategorizeTransaction()

  const rows = transactions ?? []
  const cats = categories ?? []

  // Prune the selection to ids still present whenever the row set changes
  // (filter, search, or a refetch after a mutation). Without this, stale ids
  // linger in `selectedIds` and a bulk action would target ghost rows while
  // the count badge lies. Keyed on a stable id signature so it doesn't re-run
  // on every render (rows is a fresh array each time).
  const rowIdsKey = rows.map((t) => t.id).join(',')
  useEffect(() => {
    setSelectedIds((prev) => {
      if (prev.size === 0) return prev
      const present = new Set(rows.map((t) => t.id))
      const next = new Set<string>()
      for (const id of prev) if (present.has(id)) next.add(id)
      return next.size === prev.size ? prev : next
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rowIdsKey])

  // Account filter options are derived from the (account-unfiltered) rows we
  // happen to have loaded. This is the simplest source without a separate
  // accounts query.
  const accounts = useMemo(() => deriveAccounts(rows), [rows])

  const toggle = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    setSelectedIds((prev) =>
      prev.size === rows.length
        ? new Set()
        : new Set(rows.map((t) => t.id)),
    )
  }

  const clearSelection = () => setSelectedIds(new Set())

  const handleBulkApply = (categoryId: string, categoryName: string) => {
    bulkCategorize.mutate({
      transaction_ids: [...selectedIds],
      category_id: categoryId,
      category_name: categoryName,
    })
    clearSelection()
  }

  const handleCategorizeRow = (
    id: string,
    categoryId: string | null,
    categoryName: string | null,
  ) => {
    categorizeRow.mutate({
      id,
      body: { category_id: categoryId, category_name: categoryName },
    })
  }

  return (
    <section className="p-6 space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Transactions</h1>

      <TransactionFilters
        value={filters}
        onChange={setFilters}
        accounts={accounts}
      />

      {selectedIds.size > 0 && (
        <BulkCategorizeBar
          count={selectedIds.size}
          categories={cats}
          onApply={handleBulkApply}
          onClear={clearSelection}
          pending={bulkCategorize.isPending}
        />
      )}

      {isLoading ? (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
          Loading transactions…
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
          Failed to load transactions. Please try again.
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No transactions match your filters.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <TransactionTable
            transactions={rows}
            categories={cats}
            selectedIds={selectedIds}
            onToggle={toggle}
            onToggleAll={toggleAll}
            onCategorizeRow={handleCategorizeRow}
          />
        </div>
      )}
    </section>
  )
}
