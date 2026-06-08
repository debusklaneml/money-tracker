// RulesPage — manage auto-categorization rules: create, list, delete, and
// "apply now" (run an existing rule against already-imported, uncategorized
// transactions). Data + mutations come from the spine hooks in lib/queries.

import { useState } from 'react'

import RuleForm from '../components/rules/RuleForm'
import RuleList from '../components/rules/RuleList'
import {
  useApplyRule,
  useCategories,
  useCreateRule,
  useDeleteRule,
  useRules,
} from '../lib/queries'
import type { RuleCreateRequest } from '../lib/types'

export default function RulesPage() {
  const { data: rules, isLoading, isError } = useRules()
  const { data: categories } = useCategories()
  const createRule = useCreateRule()
  const deleteRule = useDeleteRule()
  const applyRule = useApplyRule()

  const [applyMessage, setApplyMessage] = useState<string | null>(null)

  const handleCreate = (body: RuleCreateRequest) => {
    createRule.mutate(body)
  }

  const handleDelete = (id: number) => {
    if (window.confirm('Delete this rule? This cannot be undone.')) {
      deleteRule.mutate(id)
    }
  }

  const handleApply = (id: number) => {
    setApplyMessage(null)
    applyRule.mutate(id, {
      onSuccess: (res) => setApplyMessage(res.message ?? 'Rule applied.'),
    })
  }

  const list = rules ?? []
  const cats = categories ?? []
  // A single in-flight apply/delete drives the per-row busy state.
  const busyId: number | null = applyRule.isPending
    ? (applyRule.variables ?? null)
    : deleteRule.isPending
      ? (deleteRule.variables ?? null)
      : null

  return (
    <section className="p-6 space-y-4">
      <h1 className="text-2xl font-bold text-slate-900">Rules</h1>
      <p className="text-sm text-slate-500">
        Auto-categorize transactions on import. Lower priority runs first.
      </p>

      <RuleForm
        categories={cats}
        onSubmit={handleCreate}
        pending={createRule.isPending}
      />

      {applyMessage && (
        <div
          role="status"
          className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800"
        >
          {applyMessage}
        </div>
      )}

      {isLoading ? (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
          Loading rules…
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
          Failed to load rules. Please try again.
        </div>
      ) : list.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No rules yet. Add one above to auto-categorize future imports.
        </div>
      ) : (
        <RuleList
          rules={list}
          onApply={handleApply}
          onDelete={handleDelete}
          busyId={busyId}
        />
      )}
    </section>
  )
}
