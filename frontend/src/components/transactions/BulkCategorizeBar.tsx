// BulkCategorizeBar — a sticky action bar shown when one or more transaction
// rows are selected. Pick a category and apply it to every selected row, or
// clear the selection. Apply is disabled while a mutation is in flight or no
// category is chosen.

import { useState } from 'react'

import type { Category } from '../../lib/types'

interface BulkCategorizeBarProps {
  count: number
  categories: Category[]
  onApply: (categoryId: string, categoryName: string) => void
  onClear: () => void
  pending?: boolean
}

export default function BulkCategorizeBar({
  count,
  categories,
  onApply,
  onClear,
  pending = false,
}: BulkCategorizeBarProps) {
  const [categoryId, setCategoryId] = useState('')

  const handleApply = () => {
    if (categoryId === '') return
    const category = categories.find((c) => c.id === categoryId)
    onApply(categoryId, category?.name ?? '')
  }

  const disabled = pending || categoryId === ''

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
      <span className="text-sm font-medium text-emerald-800">
        {count} selected
      </span>

      <select
        aria-label="Bulk category"
        className="rounded border border-emerald-300 bg-white px-3 py-1.5 text-sm text-slate-900 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-200"
        value={categoryId}
        onChange={(e) => setCategoryId(e.target.value)}
        disabled={pending}
      >
        <option value="">Choose category…</option>
        {categories.map((category) => (
          <option key={category.id} value={category.id}>
            {category.category_group_name
              ? `${category.category_group_name}: ${category.name}`
              : category.name}
          </option>
        ))}
      </select>

      <button
        type="button"
        onClick={handleApply}
        disabled={disabled}
        className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {pending ? 'Applying…' : `Apply to ${count}`}
      </button>

      <button
        type="button"
        onClick={onClear}
        disabled={pending}
        className="rounded px-3 py-1.5 text-sm font-medium text-emerald-700 hover:bg-emerald-100 focus:outline-none focus:ring-2 focus:ring-emerald-300 disabled:opacity-50"
      >
        Clear selection
      </button>
    </div>
  )
}
