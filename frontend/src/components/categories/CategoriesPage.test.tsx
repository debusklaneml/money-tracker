import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import CategoriesPage from '../../routes/CategoriesPage'
import {
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useSetCategoryHidden,
  useUpdateCategory,
} from '../../lib/queries'
import type { Category } from '../../lib/types'

vi.mock('../../lib/queries', () => ({
  useCategories: vi.fn(),
  useCreateCategory: vi.fn(),
  useUpdateCategory: vi.fn(),
  useSetCategoryHidden: vi.fn(),
  useDeleteCategory: vi.fn(),
}))

function makeCategory(overrides: Partial<Category>): Category {
  return {
    id: 'id',
    category_group_id: null,
    category_group_name: null,
    name: 'Cat',
    hidden: false,
    budgeted: 0,
    activity: 0,
    balance: 0,
    goal_type: null,
    goal_target: null,
    goal_target_month: null,
    sort_order: 0,
    ...overrides,
  }
}

const groceries = makeCategory({
  id: 'c1',
  name: 'Groceries',
  category_group_name: 'Food',
  balance: 12000,
})
const dining = makeCategory({
  id: 'c2',
  name: 'Dining',
  category_group_name: 'Food',
  hidden: true,
  balance: 0,
})
const rent = makeCategory({
  id: 'c3',
  name: 'Rent',
  category_group_name: 'Housing',
  balance: 50000,
})

const createMutate = vi.fn()
const updateMutate = vi.fn()
const setHiddenMutate = vi.fn()
const deleteMutate = vi.fn()

function makeMutation(mutate: ReturnType<typeof vi.fn>) {
  return {
    mutate,
    mutateAsync: vi.fn().mockResolvedValue({}),
    isPending: false,
  }
}

beforeEach(() => {
  createMutate.mockReset()
  updateMutate.mockReset()
  setHiddenMutate.mockReset()
  deleteMutate.mockReset()

  vi.mocked(useCategories).mockReturnValue({
    data: [groceries, dining, rent],
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useCategories>)
  vi.mocked(useCreateCategory).mockReturnValue(
    makeMutation(createMutate) as unknown as ReturnType<typeof useCreateCategory>,
  )
  vi.mocked(useUpdateCategory).mockReturnValue(
    makeMutation(updateMutate) as unknown as ReturnType<typeof useUpdateCategory>,
  )
  vi.mocked(useSetCategoryHidden).mockReturnValue(
    makeMutation(setHiddenMutate) as unknown as ReturnType<
      typeof useSetCategoryHidden
    >,
  )
  vi.mocked(useDeleteCategory).mockReturnValue(
    makeMutation(deleteMutate) as unknown as ReturnType<typeof useDeleteCategory>,
  )
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('CategoriesPage', () => {
  it('renders categories grouped by group header, with an Unhide affordance for hidden ones', () => {
    render(<CategoriesPage />)

    expect(screen.getByText('Food')).toBeInTheDocument()
    expect(screen.getByText('Housing')).toBeInTheDocument()
    expect(screen.getByText('Groceries')).toBeInTheDocument()
    expect(screen.getByText('Rent')).toBeInTheDocument()

    // Dining is hidden → its toggle reads "Unhide".
    expect(
      screen.getByRole('button', { name: 'Unhide Dining' }),
    ).toBeInTheDocument()
    // Groceries is visible → "Hide".
    expect(
      screen.getByRole('button', { name: 'Hide Groceries' }),
    ).toBeInTheDocument()
  })

  it('creates a category from the form', async () => {
    const user = userEvent.setup()
    render(<CategoriesPage />)

    await user.click(screen.getByRole('button', { name: 'New category' }))
    await user.type(screen.getByLabelText('Category name'), 'Gas')
    await user.type(screen.getByLabelText('Category group'), 'Transport')
    await user.click(screen.getByRole('button', { name: 'Add category' }))

    expect(createMutate).toHaveBeenCalledTimes(1)
    expect(createMutate).toHaveBeenCalledWith(
      { group: 'Transport', name: 'Gas' },
      expect.anything(),
    )
  })

  it('toggles hide on a visible category', async () => {
    const user = userEvent.setup()
    render(<CategoriesPage />)

    await user.click(screen.getByRole('button', { name: 'Hide Groceries' }))

    expect(setHiddenMutate).toHaveBeenCalledWith({ id: 'c1', hidden: true })
  })

  it('deletes only when confirmed', async () => {
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<CategoriesPage />)

    await user.click(screen.getByRole('button', { name: 'Delete Rent' }))
    expect(deleteMutate).not.toHaveBeenCalled()

    confirmSpy.mockReturnValue(true)
    await user.click(screen.getByRole('button', { name: 'Delete Rent' }))
    expect(deleteMutate).toHaveBeenCalledWith('c3')
  })

  it('edits a category, seeding the form and saving an update', async () => {
    const user = userEvent.setup()
    render(<CategoriesPage />)

    await user.click(screen.getByRole('button', { name: 'Edit Groceries' }))

    const nameInput = screen.getByLabelText('Category name') as HTMLInputElement
    const groupInput = screen.getByLabelText('Category group') as HTMLInputElement
    expect(nameInput.value).toBe('Groceries')
    expect(groupInput.value).toBe('Food')

    await user.clear(nameInput)
    await user.type(nameInput, 'Food & Groceries')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(updateMutate).toHaveBeenCalledTimes(1)
    expect(updateMutate).toHaveBeenCalledWith(
      { id: 'c1', body: { name: 'Food & Groceries', group: 'Food' } },
      expect.anything(),
    )
  })

  it('reseeds the edit form when switching directly to another category', async () => {
    const user = userEvent.setup()
    render(<CategoriesPage />)

    await user.click(screen.getByRole('button', { name: 'Edit Groceries' }))
    expect(
      (screen.getByLabelText('Category name') as HTMLInputElement).value,
    ).toBe('Groceries')

    // Switch straight to editing Rent WITHOUT cancelling first — the form must
    // reseed to Rent's values, not keep Groceries' (regression guard for the
    // reused-instance bug; fixed with key={editing.id}).
    await user.click(screen.getByRole('button', { name: 'Edit Rent' }))

    const nameInput = screen.getByLabelText('Category name') as HTMLInputElement
    const groupInput = screen.getByLabelText(
      'Category group',
    ) as HTMLInputElement
    expect(nameInput.value).toBe('Rent')
    expect(groupInput.value).toBe('Housing')

    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(updateMutate).toHaveBeenCalledWith(
      { id: 'c3', body: { name: 'Rent', group: 'Housing' } },
      expect.anything(),
    )
  })

  it('shows the empty state when there are no categories', () => {
    vi.mocked(useCategories).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useCategories>)

    render(<CategoriesPage />)
    expect(screen.getByText(/no categories yet/i)).toBeInTheDocument()
  })
})
