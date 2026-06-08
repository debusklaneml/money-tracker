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

  // A single feedback channel for apply/create/delete outcomes.
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error'
    text: string
  } | null>(null)

  const errorText = (err: unknown, fallback: string) =>
    (err instanceof Error && err.message) || fallback

  const handleCreate = (body: RuleCreateRequest) => {
    setFeedback(null)
    // Return the promise so RuleForm clears the pattern only on success; also
    // surface a 400 (e.g. category not found) instead of failing silently.
    const promise = createRule.mutateAsync(body)
    promise
      .then(() => setFeedback({ type: 'success', text: 'Rule created.' }))
      .catch((err) =>
        setFeedback({
          type: 'error',
          text: errorText(err, 'Failed to create rule.'),
        }),
      )
    return promise
  }

  const handleDelete = (id: number) => {
    if (window.confirm('Delete this rule? This cannot be undone.')) {
      setFeedback(null)
      deleteRule.mutate(id, {
        onError: (err) =>
          setFeedback({
            type: 'error',
            text: errorText(err, 'Failed to delete rule.'),
          }),
      })
    }
  }

  const handleApply = (id: number) => {
    setFeedback(null)
    applyRule.mutate(id, {
      onSuccess: (res) =>
        setFeedback({ type: 'success', text: res.message ?? 'Rule applied.' }),
      onError: (err) =>
        setFeedback({
          type: 'error',
          text: errorText(err, 'Failed to apply rule.'),
        }),
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

      {feedback && (
        <div
          role={feedback.type === 'error' ? 'alert' : 'status'}
          className={
            'rounded-lg border px-4 py-2 text-sm ' +
            (feedback.type === 'error'
              ? 'border-rose-200 bg-rose-50 text-rose-800'
              : 'border-emerald-200 bg-emerald-50 text-emerald-800')
          }
        >
          {feedback.text}
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
