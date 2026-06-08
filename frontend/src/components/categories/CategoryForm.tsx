// CategoryForm — small create/edit form for a budget category.
//
// Captures a name and a group. The group field is a text input backed by a
// <datalist> of existing group names, so users can either pick an existing
// group or type a brand-new one. Submit is disabled until both fields are
// non-blank (and while a mutation is pending).

import { useId, useState } from 'react'

interface CategoryFormValues {
  name: string
  group: string
}

interface CategoryFormProps {
  mode: 'create' | 'edit'
  initial?: CategoryFormValues
  existingGroups: string[]
  onSubmit: (values: CategoryFormValues) => void
  onCancel?: () => void
  pending?: boolean
}

export default function CategoryForm({
  mode,
  initial,
  existingGroups,
  onSubmit,
  onCancel,
  pending = false,
}: CategoryFormProps) {
  const [name, setName] = useState(initial?.name ?? '')
  const [group, setGroup] = useState(initial?.group ?? '')
  const datalistId = useId()

  const disabled = pending || name.trim() === '' || group.trim() === ''

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (disabled) return
    onSubmit({ name: name.trim(), group: group.trim() })
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
    >
      <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
        Name
        <input
          aria-label="Category name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-48 rounded border border-slate-300 px-2 py-1 text-sm font-normal normal-case text-slate-900 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-200"
        />
      </label>

      <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
        Group
        <input
          aria-label="Category group"
          type="text"
          list={datalistId}
          value={group}
          onChange={(e) => setGroup(e.target.value)}
          className="w-48 rounded border border-slate-300 px-2 py-1 text-sm font-normal normal-case text-slate-900 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-200"
        />
        <datalist id={datalistId}>
          {existingGroups.map((g) => (
            <option key={g} value={g} />
          ))}
        </datalist>
      </label>

      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={disabled}
          className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {mode === 'create' ? 'Add category' : 'Save'}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}
