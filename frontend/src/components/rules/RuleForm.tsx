// RuleForm — create an auto-categorization rule. Picks a match field
// (payee/memo), a match type (contains/equals/regex), a text pattern, the
// target category, and a priority (lower runs first).

import { useState, type FormEvent } from 'react'

import type { Category, RuleCreateRequest } from '../../lib/types'

const MATCH_FIELDS = [
  { value: 'payee', label: 'Payee' },
  { value: 'memo', label: 'Memo' },
]

const MATCH_TYPES = [
  { value: 'contains', label: 'contains' },
  { value: 'equals', label: 'equals' },
  { value: 'regex', label: 'matches regex' },
]

interface RuleFormProps {
  categories: Category[]
  onSubmit: (body: RuleCreateRequest) => void
  pending?: boolean
}

const inputClass =
  'rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-200'

export default function RuleForm({
  categories,
  onSubmit,
  pending,
}: RuleFormProps) {
  const [pattern, setPattern] = useState('')
  const [matchField, setMatchField] = useState('payee')
  const [matchType, setMatchType] = useState('contains')
  const [categoryId, setCategoryId] = useState('')
  const [priority, setPriority] = useState('100')

  // Rules should target real, non-archived categories.
  const selectable = categories.filter((c) => !c.hidden)

  const canSubmit = pattern.trim() !== '' && categoryId !== '' && !pending

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    const parsedPriority = Number.parseInt(priority, 10)
    onSubmit({
      pattern: pattern.trim(),
      category_id: categoryId,
      match_field: matchField,
      match_type: matchType,
      priority: Number.isFinite(parsedPriority) ? parsedPriority : 100,
    })
    // Clear the pattern for rapid entry; keep field/type/category/priority.
    setPattern('')
  }

  return (
    <form
      onSubmit={handleSubmit}
      aria-label="Create rule"
      className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
    >
      <label className="flex flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          When
        </span>
        <select
          aria-label="Match field"
          className={inputClass}
          value={matchField}
          onChange={(e) => setMatchField(e.target.value)}
        >
          {MATCH_FIELDS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Condition
        </span>
        <select
          aria-label="Match type"
          className={inputClass}
          value={matchType}
          onChange={(e) => setMatchType(e.target.value)}
        >
          {MATCH_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-1 flex-col gap-1 min-w-[12rem]">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Pattern
        </span>
        <input
          type="text"
          aria-label="Pattern"
          placeholder="e.g. AMAZON"
          className={inputClass}
          value={pattern}
          onChange={(e) => setPattern(e.target.value)}
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Category
        </span>
        <select
          aria-label="Rule category"
          className={inputClass}
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
        >
          <option value="">Select category…</option>
          {selectable.map((c) => (
            <option key={c.id} value={c.id}>
              {c.category_group_name
                ? `${c.category_group_name}: ${c.name}`
                : c.name}
            </option>
          ))}
        </select>
      </label>

      <label className="flex w-20 flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Priority
        </span>
        <input
          type="number"
          aria-label="Priority"
          className={inputClass}
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
        />
      </label>

      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {pending ? 'Adding…' : 'Add rule'}
      </button>
    </form>
  )
}
