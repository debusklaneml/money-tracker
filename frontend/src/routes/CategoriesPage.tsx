// CategoriesPage — CRUD over budget categories.
//
// Lists categories grouped by group (CategoryList), and supports creating a
// new category, renaming / moving a category to another group, hiding /
// unhiding (archiving), and deleting. All data + mutations come from the
// existing spine hooks in lib/queries.

import { useMemo, useState } from 'react'

import CategoryForm from '../components/categories/CategoryForm'
import CategoryList from '../components/categories/CategoryList'
import {
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useSetCategoryHidden,
  useUpdateCategory,
} from '../lib/queries'
import type { Category } from '../lib/types'

export default function CategoriesPage() {
  const { data, isLoading, isError } = useCategories()
  const createCategory = useCreateCategory()
  const updateCategory = useUpdateCategory()
  const setHidden = useSetCategoryHidden()
  const deleteCategory = useDeleteCategory()

  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Category | null>(null)

  const categories = data ?? []

  const existingGroups = useMemo(() => {
    const seen = new Set<string>()
    const groups: string[] = []
    for (const c of categories) {
      const g = c.category_group_name
      if (g && !seen.has(g)) {
        seen.add(g)
        groups.push(g)
      }
    }
    return groups
  }, [categories])

  const handleCreate = (values: { name: string; group: string }) => {
    createCategory.mutate(
      { group: values.group, name: values.name },
      { onSuccess: () => setCreating(false) },
    )
  }

  const handleEditSubmit = (values: { name: string; group: string }) => {
    if (!editing) return
    updateCategory.mutate(
      { id: editing.id, body: { name: values.name, group: values.group } },
      { onSuccess: () => setEditing(null) },
    )
  }

  const handleToggleHidden = (c: Category) => {
    setHidden.mutate({ id: c.id, hidden: !c.hidden })
  }

  const handleDelete = (c: Category) => {
    if (window.confirm(`Delete category "${c.name}"? This cannot be undone.`)) {
      deleteCategory.mutate(c.id)
    }
  }

  return (
    <section className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Categories</h1>
        {!creating && !editing && (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
          >
            New category
          </button>
        )}
      </div>

      {creating && (
        <CategoryForm
          mode="create"
          existingGroups={existingGroups}
          onSubmit={handleCreate}
          onCancel={() => setCreating(false)}
          pending={createCategory.isPending}
        />
      )}

      {editing && (
        <CategoryForm
          key={editing.id}
          mode="edit"
          initial={{
            name: editing.name,
            group: editing.category_group_name ?? '',
          }}
          existingGroups={existingGroups}
          onSubmit={handleEditSubmit}
          onCancel={() => setEditing(null)}
          pending={updateCategory.isPending}
        />
      )}

      {isLoading ? (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
          Loading categories…
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-sm text-rose-700">
          Failed to load categories. Please try again.
        </div>
      ) : categories.length === 0 ? (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No categories yet. Create a category to get started.
        </div>
      ) : (
        <CategoryList
          categories={categories}
          onEdit={(c) => {
            setCreating(false)
            setEditing(c)
          }}
          onToggleHidden={handleToggleHidden}
          onDelete={handleDelete}
        />
      )}
    </section>
  )
}
