import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import ImportPage from '../../routes/ImportPage'
import type {
  ImportBatch,
  ImportPreview,
  ImportResult,
  Transaction,
} from '../../lib/types'

vi.mock('../../lib/queries', () => ({
  usePreviewImport: vi.fn(),
  useCommitImport: vi.fn(),
  useImportHistory: vi.fn(),
  useDeleteImport: vi.fn(),
}))

import {
  usePreviewImport,
  useCommitImport,
  useImportHistory,
  useDeleteImport,
} from '../../lib/queries'

const mockedPreview = vi.mocked(usePreviewImport)
const mockedCommit = vi.mocked(useCommitImport)
const mockedHistory = vi.mocked(useImportHistory)
const mockedDeleteImport = vi.mocked(useDeleteImport)

function makeTxn(over: Partial<Transaction> = {}): Transaction {
  return {
    id: 't1',
    account_id: 'a1',
    account_name: 'Checking',
    date: '2026-05-01',
    amount: -4250,
    memo: 'coffee',
    cleared: null,
    approved: false,
    flag_color: null,
    payee_id: null,
    payee_name: 'Blue Bottle',
    category_id: null,
    category_name: null,
    transfer_account_id: null,
    transfer_transaction_id: null,
    import_id: null,
    deleted: false,
    ...over,
  }
}

const samplePreview: ImportPreview = {
  filename: 'statement.ofx',
  accounts: ['Checking 1234', 'Savings 5678'],
  new_transactions: [
    makeTxn({ id: 't1', payee_name: 'Blue Bottle', amount: -4250 }),
    makeTxn({ id: 't2', payee_name: 'Paycheck', amount: 250000 }),
  ],
  duplicate_count: 3,
  already_imported_file: false,
  date_min: '2026-05-01',
  date_max: '2026-05-31',
}

const sampleResult: ImportResult = {
  filename: 'statement.ofx',
  accounts: ['Checking 1234'],
  imported: 12,
  duplicates: 3,
  auto_categorized: 7,
  already_imported_file: false,
  date_min: '2026-05-01',
  date_max: '2026-05-31',
}

const sampleBatches: ImportBatch[] = [
  {
    id: 1,
    account_id: 'a1',
    filename: 'march.ofx',
    file_hash: 'abc',
    imported_at: '2026-03-15T10:00:00Z',
    txn_count: 42,
    duplicate_count: 2,
    date_min: '2026-03-01',
    date_max: '2026-03-31',
  },
]

let previewMutate: ReturnType<typeof vi.fn>
let previewMutateAsync: ReturnType<typeof vi.fn>
let previewReset: ReturnType<typeof vi.fn>
let commitMutateAsync: ReturnType<typeof vi.fn>
let commitReset: ReturnType<typeof vi.fn>
let deleteImportMutateAsync: ReturnType<typeof vi.fn>

interface PreviewOverrides {
  data?: ImportPreview
  isPending?: boolean
  isError?: boolean
  error?: unknown
}

interface CommitOverrides {
  data?: ImportResult
  isPending?: boolean
  isError?: boolean
  error?: unknown
}

interface HistoryOverrides {
  data?: ImportBatch[]
  isLoading?: boolean
  isError?: boolean
}

interface DeleteImportOverrides {
  isPending?: boolean
  isError?: boolean
  variables?: number
}

function setup(opts: {
  preview?: PreviewOverrides
  commit?: CommitOverrides
  history?: HistoryOverrides
  deleteImport?: DeleteImportOverrides
} = {}) {
  previewMutate = vi.fn()
  previewMutateAsync = vi.fn().mockResolvedValue(samplePreview)
  previewReset = vi.fn()
  commitMutateAsync = vi.fn().mockResolvedValue(sampleResult)
  commitReset = vi.fn()
  deleteImportMutateAsync = vi
    .fn()
    .mockResolvedValue({ id: 1, deleted_transactions: 42 })

  mockedPreview.mockReturnValue({
    mutate: previewMutate,
    mutateAsync: previewMutateAsync,
    reset: previewReset,
    data: opts.preview?.data,
    isPending: opts.preview?.isPending ?? false,
    isError: opts.preview?.isError ?? false,
    error: opts.preview?.error ?? null,
  } as unknown as ReturnType<typeof usePreviewImport>)

  mockedCommit.mockReturnValue({
    mutate: vi.fn(),
    mutateAsync: commitMutateAsync,
    reset: commitReset,
    data: opts.commit?.data,
    isPending: opts.commit?.isPending ?? false,
    isError: opts.commit?.isError ?? false,
    error: opts.commit?.error ?? null,
  } as unknown as ReturnType<typeof useCommitImport>)

  mockedHistory.mockReturnValue({
    data: opts.history?.data ?? sampleBatches,
    isLoading: opts.history?.isLoading ?? false,
    isError: opts.history?.isError ?? false,
  } as unknown as ReturnType<typeof useImportHistory>)

  mockedDeleteImport.mockReturnValue({
    mutate: vi.fn(),
    mutateAsync: deleteImportMutateAsync,
    reset: vi.fn(),
    isPending: opts.deleteImport?.isPending ?? false,
    isError: opts.deleteImport?.isError ?? false,
    variables: opts.deleteImport?.variables,
  } as unknown as ReturnType<typeof useDeleteImport>)
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ImportPage', () => {
  it('renders the heading, the dropzone, and history rows', () => {
    setup()
    render(<ImportPage />)

    expect(
      screen.getByRole('heading', { name: 'Import', level: 1 }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Upload OFX or QFX file' }),
    ).toBeInTheDocument()

    const history = screen.getByTestId('import-history')
    expect(within(history).getByText('march.ofx')).toBeInTheDocument()
    expect(within(history).getByText('42')).toBeInTheDocument()
  })

  it('selecting a file triggers the preview mutation with the File', async () => {
    setup()
    render(<ImportPage />)

    const input = screen.getByLabelText(
      'OFX or QFX file input',
    ) as HTMLInputElement
    const file = new File(['x'], 'statement.ofx', { type: 'application/x-ofx' })

    await userEvent.upload(input, file)

    expect(previewMutate).toHaveBeenCalledTimes(1)
    expect(previewMutate).toHaveBeenCalledWith(file)
  })

  it('renders the preview table (accounts + a transaction amount) when preview data is present', () => {
    setup({ preview: { data: samplePreview } })
    render(<ImportPage />)

    expect(screen.getByText('Checking 1234')).toBeInTheDocument()
    expect(screen.getByText('Savings 5678')).toBeInTheDocument()
    expect(screen.getByText('Blue Bottle')).toBeInTheDocument()
    // Outflow formatted by formatMoney(-4250).
    expect(screen.getByText('-$4.25')).toBeInTheDocument()
    // Inflow.
    expect(screen.getByText('$250.00')).toBeInTheDocument()
    // Summary line.
    expect(screen.getByTestId('preview-summary')).toHaveTextContent('2 new')
    expect(screen.getByTestId('preview-summary')).toHaveTextContent(
      '3 duplicates',
    )
  })

  it('clicking "Commit import" calls the commit mutation with the selected file', async () => {
    // The preview hook is mocked to already report data, so once a file is
    // selected the page holds it in state AND shows the preview + commit button.
    setup({ preview: { data: samplePreview } })
    render(<ImportPage />)

    const input = screen.getByLabelText(
      'OFX or QFX file input',
    ) as HTMLInputElement
    const file = new File(['x'], 'statement.ofx', { type: 'application/x-ofx' })
    await userEvent.upload(input, file)

    // file→preview→commit wiring: preview.mutate fired with the File...
    expect(previewMutate).toHaveBeenCalledWith(file)

    const commitBtn = await screen.findByRole('button', {
      name: 'Commit import',
    })
    await userEvent.click(commitBtn)

    // ...and committing fires commit.mutateAsync with the same File.
    expect(commitMutateAsync).toHaveBeenCalledTimes(1)
    expect(commitMutateAsync).toHaveBeenCalledWith(file)
  })

  it('shows the "already imported" warning when already_imported_file is true', () => {
    setup({
      preview: { data: { ...samplePreview, already_imported_file: true } },
    })
    render(<ImportPage />)

    expect(
      screen.getByText(/already been imported/i),
    ).toBeInTheDocument()
  })

  it('shows a success summary after a commit resolves', () => {
    setup({ commit: { data: sampleResult } })
    render(<ImportPage />)

    expect(screen.getByText(/Imported statement\.ofx/)).toBeInTheDocument()
    expect(
      screen.getByText(/12 imported · 3 duplicates · 7 auto-categorized/),
    ).toBeInTheDocument()
  })

  it('shows the commit error message when commit fails', () => {
    setup({
      preview: { data: samplePreview },
      commit: { isError: true, error: new Error('server exploded') },
    })
    render(<ImportPage />)

    expect(screen.getByText(/Import failed: server exploded/)).toBeInTheDocument()
  })

  it('retains the file and preview for retry when the commit rejects', async () => {
    setup({ preview: { data: samplePreview } })
    commitMutateAsync.mockRejectedValueOnce(new Error('boom'))
    render(<ImportPage />)

    const input = screen.getByLabelText(
      'OFX or QFX file input',
    ) as HTMLInputElement
    const file = new File(['x'], 'statement.ofx', { type: 'application/x-ofx' })
    await userEvent.upload(input, file)

    const commitBtn = await screen.findByRole('button', {
      name: 'Commit import',
    })
    await userEvent.click(commitBtn)

    // The rejection is handled (no unhandled promise) and state is retained:
    // preview.reset() only runs on a SUCCESSFUL commit, so it must not fire here.
    await waitFor(() => expect(commitMutateAsync).toHaveBeenCalledWith(file))
    expect(previewReset).not.toHaveBeenCalled()
    // Commit stays available so the user can retry.
    expect(
      screen.getByRole('button', { name: 'Commit import' }),
    ).toBeInTheDocument()
  })

  it('caps the preview table at 100 rows and notes how many are hidden', () => {
    const many = Array.from({ length: 150 }, (_, i) =>
      makeTxn({ id: `t${i}`, payee_name: `Payee-${i}`, amount: -1000 }),
    )
    setup({ preview: { data: { ...samplePreview, new_transactions: many } } })
    render(<ImportPage />)

    const note = screen.getByTestId('row-cap-note')
    expect(note).toHaveTextContent('Showing first 100 of 150')
    expect(note).toHaveTextContent('+50')
    // The first row renders; the 150th (beyond the cap) does not.
    expect(screen.getByText('Payee-0')).toBeInTheDocument()
    expect(screen.queryByText('Payee-149')).not.toBeInTheDocument()
  })
})

describe('ImportHistory states', () => {
  it('shows the loading state', () => {
    setup({ history: { isLoading: true, data: [] } })
    render(<ImportPage />)
    expect(screen.getByText(/Loading import history/i)).toBeInTheDocument()
  })

  it('shows the empty state', () => {
    setup({ history: { data: [] } })
    render(<ImportPage />)
    expect(screen.getByText(/No imports yet/i)).toBeInTheDocument()
  })

  it('shows the error state', () => {
    setup({ history: { isError: true, data: [] } })
    render(<ImportPage />)
    expect(
      screen.getByText(/Failed to load import history/i),
    ).toBeInTheDocument()
  })
})

describe('ImportHistory delete', () => {
  it('requires a confirmation before deleting, then calls the mutation with the batch id', async () => {
    setup()
    render(<ImportPage />)

    // First click only reveals the confirm affordance — no mutation yet.
    await userEvent.click(
      screen.getByRole('button', { name: /Delete march\.ofx/i }),
    )
    expect(deleteImportMutateAsync).not.toHaveBeenCalled()
    expect(screen.getByText(/Delete 42 txns\?/i)).toBeInTheDocument()

    // Confirm fires the delete with the batch id.
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    await waitFor(() =>
      expect(deleteImportMutateAsync).toHaveBeenCalledWith(1),
    )
  })

  it('cancel dismisses the confirmation without deleting', async () => {
    setup()
    render(<ImportPage />)

    await userEvent.click(
      screen.getByRole('button', { name: /Delete march\.ofx/i }),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(deleteImportMutateAsync).not.toHaveBeenCalled()
    expect(screen.queryByText(/Delete 42 txns\?/i)).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Delete march\.ofx/i }),
    ).toBeInTheDocument()
  })

  it('surfaces an error banner when the delete fails', () => {
    setup({ deleteImport: { isError: true } })
    render(<ImportPage />)
    expect(
      screen.getByText(/Failed to delete the upload/i),
    ).toBeInTheDocument()
  })
})
