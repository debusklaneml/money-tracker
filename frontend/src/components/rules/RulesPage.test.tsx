import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import RulesPage from '../../routes/RulesPage'
import type { Category, Rule } from '../../lib/types'

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

let createMutate: ReturnType<typeof vi.fn>
let deleteMutate: ReturnType<typeof vi.fn>
let applyMutate: ReturnType<typeof vi.fn>

function mutation(mutate: ReturnType<typeof vi.fn>, extra: object = {}) {
  return {
    mutate,
    mutateAsync: vi.fn().mockResolvedValue({}),
    isPending: false,
    variables: undefined,
    ...extra,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  createMutate = vi.fn()
  deleteMutate = vi.fn()
  // apply: invoke the onSuccess option with a result so the page can surface it.
  applyMutate = vi.fn((_id: number, opts?: { onSuccess?: (r: unknown) => void }) =>
    opts?.onSuccess?.({
      status: 'ok',
      message: 'Applied rule to 5 transactions',
    }),
  )

  mockedUseRules.mockReturnValue({
    data: sampleRules,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useRules>)
  mockedUseCategories.mockReturnValue({
    data: sampleCategories,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useCategories>)
  mockedUseCreateRule.mockReturnValue(
    mutation(createMutate) as unknown as ReturnType<typeof useCreateRule>,
  )
  mockedUseDeleteRule.mockReturnValue(
    mutation(deleteMutate) as unknown as ReturnType<typeof useDeleteRule>,
  )
  mockedUseApplyRule.mockReturnValue(
    mutation(applyMutate) as unknown as ReturnType<typeof useApplyRule>,
  )
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
    await user.type(screen.getByRole('textbox', { name: 'Pattern' }), 'STARBUCKS')
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Rule category' }),
      'c2',
    )
    await user.click(screen.getByRole('button', { name: 'Add rule' }))

    expect(createMutate).toHaveBeenCalledTimes(1)
    expect(createMutate).toHaveBeenCalledWith({
      pattern: 'STARBUCKS',
      category_id: 'c2',
      match_field: 'memo',
      match_type: 'equals',
      priority: 100,
    })
  })

  it('does not submit when pattern or category is missing', async () => {
    const user = userEvent.setup()
    render(<RulesPage />)

    // No pattern, no category chosen → button disabled, submit is a no-op.
    await user.click(screen.getByRole('button', { name: 'Add rule' }))
    expect(createMutate).not.toHaveBeenCalled()
  })

  it('applies a rule and surfaces the returned count message', async () => {
    const user = userEvent.setup()
    render(<RulesPage />)

    await user.click(screen.getByRole('button', { name: 'Apply rule 1' }))

    expect(applyMutate).toHaveBeenCalledWith(1, expect.anything())
    expect(
      await screen.findByText('Applied rule to 5 transactions'),
    ).toBeInTheDocument()
  })

  it('deletes a rule only when confirmed', async () => {
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<RulesPage />)

    await user.click(screen.getByRole('button', { name: 'Delete rule 2' }))
    expect(deleteMutate).not.toHaveBeenCalled()

    confirmSpy.mockReturnValue(true)
    await user.click(screen.getByRole('button', { name: 'Delete rule 2' }))
    expect(deleteMutate).toHaveBeenCalledWith(2)

    confirmSpy.mockRestore()
  })

  it('shows the empty state when there are no rules', () => {
    mockedUseRules.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useRules>)
    render(<RulesPage />)
    expect(screen.getByText(/no rules yet/i)).toBeInTheDocument()
  })
})
