import { describe, it, expect, beforeEach, vi } from 'vitest'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import RulesPage from '../../routes/RulesPage'
import type { Category, MessageResponse, Rule } from '../../lib/types'

vi.mock('../../lib/queries', () => ({
  useRules: vi.fn(),
  useCategories: vi.fn(),
  useCreateRule: vi.fn(),
  useDeleteRule: vi.fn(),
  useApplyRule: vi.fn(),
}))

import {
  useRules,
  useCategories,
  useCreateRule,
  useDeleteRule,
  useApplyRule,
} from '../../lib/queries'

const mockedUseRules = vi.mocked(useRules)
const mockedUseCategories = vi.mocked(useCategories)
const mockedUseCreateRule = vi.mocked(useCreateRule)
const mockedUseDeleteRule = vi.mocked(useDeleteRule)
const mockedUseApplyRule = vi.mocked(useApplyRule)

const sampleRules: Rule[] = [
  {
    id: 1,
    match_field: 'payee',
    match_type: 'contains',
    pattern: 'AMAZON',
    category_id: 'c1',
    category_name: 'Shopping',
    group_name: 'Everyday',
    priority: 100,
  },
  {
    id: 2,
    match_field: 'memo',
    match_type: 'regex',
    pattern: '^ACH',
    category_id: 'c2',
    category_name: 'Bills',
    group_name: 'Monthly',
    priority: 50,
  },
]

function makeCategory(over: Partial<Category>): Category {
  return {
    id: 'c1',
    category_group_id: 'g1',
    category_group_name: 'Everyday',
    name: 'Shopping',
    hidden: false,
    budgeted: 0,
    activity: 0,
    balance: 0,
    goal_type: null,
    goal_target: null,
    goal_target_month: null,
    sort_order: 0,
    ...over,
  }
}

const sampleCategories: Category[] = [
  makeCategory({ id: 'c1', name: 'Shopping', category_group_name: 'Everyday' }),
  makeCategory({ id: 'c2', name: 'Bills', category_group_name: 'Monthly' }),
  makeCategory({ id: 'c3', name: 'Archived', hidden: true }),
]

let createMutateAsync: ReturnType<typeof vi.fn>
let deleteMutate: ReturnType<typeof vi.fn>
let applyMutate: ReturnType<typeof vi.fn>

function setHooks(
  over: {
    rules?: Partial<ReturnType<typeof useRules>>
    create?: Record<string, unknown>
    del?: Record<string, unknown>
    apply?: Record<string, unknown>
  } = {},
) {
  mockedUseRules.mockReturnValue({
    data: sampleRules,
    isLoading: false,
    isError: false,
    ...over.rules,
  } as unknown as ReturnType<typeof useRules>)
  mockedUseCategories.mockReturnValue({
    data: sampleCategories,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useCategories>)
  mockedUseCreateRule.mockReturnValue({
    mutate: vi.fn(),
    mutateAsync: createMutateAsync,
    isPending: false,
    variables: undefined,
    ...over.create,
  } as unknown as ReturnType<typeof useCreateRule>)
  mockedUseDeleteRule.mockReturnValue({
    mutate: deleteMutate,
    mutateAsync: vi.fn(),
    isPending: false,
    variables: undefined,
    ...over.del,
  } as unknown as ReturnType<typeof useDeleteRule>)
  mockedUseApplyRule.mockReturnValue({
    mutate: applyMutate,
    mutateAsync: vi.fn(),
    isPending: false,
    variables: undefined,
    ...over.apply,
  } as unknown as ReturnType<typeof useApplyRule>)
}

async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByRole('textbox', { name: 'Pattern' }), 'STARBUCKS')
  await user.selectOptions(
    screen.getByRole('combobox', { name: 'Rule category' }),
    'c2',
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  createMutateAsync = vi.fn().mockResolvedValue({})
  deleteMutate = vi.fn()
  applyMutate = vi.fn()
  setHooks()
})

describe('RulesPage', () => {
  it('renders rules with their condition text and category', () => {
    render(<RulesPage />)

    const list = within(screen.getByTestId('rule-list'))
    expect(list.getByText('payee contains "AMAZON"')).toBeInTheDocument()
    expect(list.getByText('memo matches regex "^ACH"')).toBeInTheDocument()
    // Category labels also appear in the form's <option>s, so scope to the list.
    expect(list.getByText('Everyday: Shopping')).toBeInTheDocument()
    expect(list.getByText('Monthly: Bills')).toBeInTheDocument()
  })

  it('omits hidden categories from the rule category picker', () => {
    render(<RulesPage />)
    const select = screen.getByRole('combobox', { name: 'Rule category' })
    expect(select).toHaveTextContent('Everyday: Shopping')
    expect(select).toHaveTextContent('Monthly: Bills')
    expect(select).not.toHaveTextContent('Archived')
  })

  it('creates a rule from the form with the chosen field/type/category', async () => {
    const user = userEvent.setup()
    render(<RulesPage />)

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Match field' }),
      'memo',
    )
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Match type' }),
      'equals',
    )
    await fillRequiredFields(user)
    await user.click(screen.getByRole('button', { name: 'Add rule' }))

    expect(createMutateAsync).toHaveBeenCalledTimes(1)
    expect(createMutateAsync).toHaveBeenCalledWith({
      pattern: 'STARBUCKS',
      category_id: 'c2',
      match_field: 'memo',
      match_type: 'equals',
      priority: 100,
    })
  })

  it('sends a custom priority as a number and clamps negatives', async () => {
    const user = userEvent.setup()
    render(<RulesPage />)

    const priority = screen.getByRole('spinbutton', { name: 'Priority' })
    await user.clear(priority)
    await user.type(priority, '5')
    await fillRequiredFields(user)
    await user.click(screen.getByRole('button', { name: 'Add rule' }))

    expect(createMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ priority: 5 }),
    )
  })

  it('clears the pattern on success but keeps it when the create fails', async () => {
    const user = userEvent.setup()
    // First create rejects (e.g. a 400 from the backend).
    createMutateAsync.mockRejectedValueOnce(new Error("Category 'c2' not found"))
    render(<RulesPage />)

    const pattern = screen.getByRole('textbox', {
      name: 'Pattern',
    }) as HTMLInputElement
    await fillRequiredFields(user)
    await user.click(screen.getByRole('button', { name: 'Add rule' }))

    // Error surfaced and the pattern is retained for a retry.
    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Category 'c2' not found",
    )
    expect(pattern.value).toBe('STARBUCKS')

    // A subsequent successful create clears the pattern.
    await user.click(screen.getByRole('button', { name: 'Add rule' }))
    await screen.findByRole('status')
    expect(pattern.value).toBe('')
  })

  it('does not submit when pattern or category is missing', async () => {
    const user = userEvent.setup()
    render(<RulesPage />)

    await user.click(screen.getByRole('button', { name: 'Add rule' }))
    expect(createMutateAsync).not.toHaveBeenCalled()
  })

  it('applies a rule and surfaces the server count message via the page wiring', async () => {
    const user = userEvent.setup()
    render(<RulesPage />)

    await user.click(screen.getByRole('button', { name: 'Apply rule 1' }))
    expect(applyMutate).toHaveBeenCalledWith(1, expect.any(Object))

    // Drive the page's own onSuccess with a realistic MessageResponse — this
    // proves the page reads res.message, not just that a mock echoes a string.
    const opts = applyMutate.mock.calls[0][1] as {
      onSuccess: (r: MessageResponse) => void
    }
    act(() =>
      opts.onSuccess({
        status: 'ok',
        message: 'Applied rule to 5 transactions',
      }),
    )

    expect(screen.getByRole('status')).toHaveTextContent(
      'Applied rule to 5 transactions',
    )
  })

  it('surfaces an error when applying a rule fails', async () => {
    const user = userEvent.setup()
    render(<RulesPage />)

    await user.click(screen.getByRole('button', { name: 'Apply rule 2' }))
    const opts = applyMutate.mock.calls[0][1] as {
      onError: (e: Error) => void
    }
    act(() => opts.onError(new Error('Rule 2 not found')))

    expect(screen.getByRole('alert')).toHaveTextContent('Rule 2 not found')
  })

  it('deletes a rule only when confirmed', async () => {
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<RulesPage />)

    await user.click(screen.getByRole('button', { name: 'Delete rule 2' }))
    expect(deleteMutate).not.toHaveBeenCalled()

    confirmSpy.mockReturnValue(true)
    await user.click(screen.getByRole('button', { name: 'Delete rule 2' }))
    expect(deleteMutate).toHaveBeenCalledWith(2, expect.any(Object))

    confirmSpy.mockRestore()
  })

  it('disables only the busy row while an apply is in flight', () => {
    setHooks({ apply: { isPending: true, variables: 1 } })
    render(<RulesPage />)

    expect(screen.getByRole('button', { name: 'Apply rule 1' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Delete rule 1' })).toBeDisabled()
    // The other row stays interactive.
    expect(
      screen.getByRole('button', { name: 'Apply rule 2' }),
    ).not.toBeDisabled()
  })

  it('shows the loading state', () => {
    setHooks({ rules: { data: undefined, isLoading: true, isError: false } })
    render(<RulesPage />)
    expect(screen.getByText(/loading rules/i)).toBeInTheDocument()
  })

  it('shows the error state', () => {
    setHooks({ rules: { data: undefined, isLoading: false, isError: true } })
    render(<RulesPage />)
    expect(screen.getByText(/failed to load rules/i)).toBeInTheDocument()
  })

  it('shows the empty state when there are no rules', () => {
    setHooks({ rules: { data: [], isLoading: false, isError: false } })
    render(<RulesPage />)
    expect(screen.getByText(/no rules yet/i)).toBeInTheDocument()
  })
})
