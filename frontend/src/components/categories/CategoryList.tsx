// CategoryList — categories grouped by their group with per-row actions.
//
// Mirrors EnvelopeGrid's grouped-table conventions (slate/emerald palette, a
// group header row preceding each group's rows). Each row shows the category
// name (struck-through + muted when hidden), its balance, and Edit / Hide
// (or Unhide) / Delete actions with category-scoped accessible names.

import { useMemo } from 'react'

import { formatMoney } from '../../lib/money'
import type { Category } from '../../lib/types'

const UNGROUPED_LABEL = 'Ungrouped'

interface CategoryListProps {
  categories: Category[]
  onEdit: (c: Category) => void
  onToggleHidden: (c: Category) => void
  onDelete: (c: Category) => void
}

export default function CategoryList({
  categories,
  onEdit,
  onToggleHidden,
  onDelete,
}: CategoryListProps) {
  // Pre-group in memory, preserving first-seen group order.
  const groups = useMemo(() => {
    const order: string[] = []
    const byGroup = new Map<string, Category[]>()
    for (const c of categories) {
      const key = c.category_group_name ?? UNGROUPED_LABEL
      let bucket = byGroup.get(key)
      if (!bucket) {
        bucket = []
        byGroup.set(key, bucket)
        order.push(key)
      }
      bucket.push(c)
    }
    return order.map((name) => ({ name, rows: byGroup.get(name)! }))
  }, [categories])

  return (
    <table
      data-testid="category-list"
      className="w-full border-collapse text-left"
    >
      <thead>
        <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wide text-slate-400">
          <th scope="col" className="px-3 py-2 text-left">
            Category
          </th>
          <th scope="col" className="px-3 py-2 text-right">
            Balance
          </th>
          <th scope="col" className="px-3 py-2 text-right">
            Actions
          </th>
        </tr>
      </thead>

      {groups.map((group) => (
        <tbody key={group.name}>
          <tr className="bg-slate-50">
            <th
              scope="colgroup"
              colSpan={3}
              className="px-3 py-2 text-left text-sm font-semibold text-slate-700"
            >
              {group.name}
            </th>
          </tr>

          {group.rows.map((c) => (
            <tr
              key={c.id}
              className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60"
            >
              <td className="px-3 py-2 align-middle text-left">
                <span
                  className={
                    'text-sm ' +
                    (c.hidden
                      ? 'text-slate-400 line-through'
                      : 'text-slate-800')
                  }
                >
                  {c.name}
                </span>
              </td>
              <td className="px-3 py-2 align-middle text-right text-sm tabular-nums text-slate-500">
                {formatMoney(c.balance)}
              </td>
              <td className="px-3 py-2 align-middle text-right">
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    aria-label={`Edit ${c.name}`}
                    onClick={() => onEdit(c)}
                    className="rounded px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    aria-label={`${c.hidden ? 'Unhide' : 'Hide'} ${c.name}`}
                    onClick={() => onToggleHidden(c)}
                    className="rounded px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
                  >
                    {c.hidden ? 'Unhide' : 'Hide'}
                  </button>
                  <button
                    type="button"
                    aria-label={`Delete ${c.name}`}
                    onClick={() => onDelete(c)}
                    className="rounded px-2 py-1 text-xs font-medium text-rose-600 hover:bg-rose-50"
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      ))}
    </table>
  )
}
