// TransactionFilters — search/account/uncategorized controls for the
// Transactions page. The search input is debounced (~250ms) so typing doesn't
// re-query on every keystroke; the account select and the "uncategorized only"
// checkbox apply immediately.

import { useEffect, useRef, useState } from 'react'

export interface Filters {
  search: string
  account_id?: string
  uncategorized: boolean
}

interface TransactionFiltersProps {
  value: Filters
  onChange: (next: Filters) => void
  accounts: { id: string; name: string }[]
}

const SEARCH_DEBOUNCE_MS = 250

export default function TransactionFilters({
  value,
  onChange,
  accounts,
}: TransactionFiltersProps) {
  // Local, immediately-controlled draft of the search box. We debounce the
  // propagation upward so the query params (and network) only churn after the
  // user pauses typing.
  const [searchDraft, setSearchDraft] = useState(value.search)

  // Keep the draft in sync if the parent resets the filter externally.
  useEffect(() => {
    setSearchDraft(value.search)
  }, [value.search])

  // Latest value/onChange captured for the debounced flush without re-arming
  // the timer on every render.
  const valueRef = useRef(value)
  const onChangeRef = useRef(onChange)
  valueRef.current = value
  onChangeRef.current = onChange

  const handleSearchChange = (next: string) => {
    setSearchDraft(next)
  }

  // Debounced flush: whenever the draft differs from the committed search,
  // schedule an onChange and clean it up if the draft changes again.
  useEffect(() => {
    if (searchDraft === valueRef.current.search) return
    const handle = setTimeout(() => {
      onChangeRef.current({ ...valueRef.current, search: searchDraft })
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(handle)
  }, [searchDraft])

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4">
      <label className="flex flex-1 flex-col gap-1 min-w-[12rem]">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Search
        </span>
        <input
          type="search"
          aria-label="Search transactions"
          placeholder="Payee or memo…"
          className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-200"
          value={searchDraft}
          onChange={(e) => handleSearchChange(e.target.value)}
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Account
        </span>
        <select
          aria-label="Filter by account"
          className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-200"
          value={value.account_id ?? ''}
          onChange={(e) =>
            onChange({
              ...value,
              account_id: e.target.value === '' ? undefined : e.target.value,
            })
          }
        >
          <option value="">All accounts</option>
          {accounts.map((account) => (
            <option key={account.id} value={account.id}>
              {account.name}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-2 py-1.5 text-sm text-slate-700">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-200"
          checked={value.uncategorized}
          onChange={(e) =>
            onChange({ ...value, uncategorized: e.target.checked })
          }
        />
        Uncategorized only
      </label>
    </div>
  )
}
