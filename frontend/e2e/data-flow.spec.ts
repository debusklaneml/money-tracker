import { test, expect } from '@playwright/test'

/**
 * Phase 5 data happy-path against the single-process FastAPI server, running on
 * a clean throwaway DB (see playwright.config.ts `BUD_DB_PATH`). This is the
 * end-to-end flow the app exists for:
 *
 *   import OFX  →  categorize a transaction  →  assign money in the budget
 *              →  Ready-to-Assign and the category's Available update
 *              →  re-importing the same file reports duplicates (FITID dedup)
 *
 * The numbers are deterministic because the DB starts empty + freshly seeded
 * with the default categories. The OFX fixture has exactly two transactions:
 *   • a +$1,500.00 credit (uncategorized → counts as income → drives RTA)
 *   • a  -$42.50 debit at "Coffee Shop" (we categorize it into Wants: Dining Out)
 *
 * Budget math (see src/budget/engine.py):
 *   income_total = 1500.00, assigned_total starts at 0  → RTA = $1,500.00
 *   assign $50.00 to Dining Out                         → RTA = $1,450.00
 *   Dining Out Available = assigned 50.00 + activity -42.50 = $7.50
 *   (spending does NOT reduce RTA; it reduces the category's Available)
 */

// Transactions must fall in the current budget month (BudgetPage defaults to
// the current month, and activity is month-scoped), so stamp the OFX with the
// current year-month and a mid-month day that always exists.
const now = new Date()
const STAMP = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}15`

const OFX = `OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<CURDEF>USD
<BANKACCTFROM>
<ACCTID>E2E-CHECKING-001
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>${STAMP}
<TRNAMT>1500.00
<FITID>E2E-INCOME-001
<NAME>Employer Payroll
<MEMO>Salary
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>${STAMP}
<TRNAMT>-42.50
<FITID>E2E-COFFEE-001
<NAME>Coffee Shop
<MEMO>Latte
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>1457.50
<DTASOF>${STAMP}
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>`

const OFX_FILE = {
  name: 'statement.ofx',
  mimeType: 'application/x-ofx',
  buffer: Buffer.from(OFX, 'utf-8'),
}

function nav(page: import('@playwright/test').Page) {
  return page.getByRole('navigation', { name: 'Main navigation' })
}

test('import → categorize → assign updates RTA & Available; re-import reports duplicates', async ({
  page,
}) => {
  // --- 1. IMPORT ----------------------------------------------------------
  await page.goto('/import')
  await expect(page.getByRole('heading', { name: 'Import', exact: true })).toBeVisible()

  await page.getByLabel('OFX or QFX file input').setInputFiles(OFX_FILE)

  // Non-committing preview: two new transactions, nothing duplicate yet.
  const previewSummary = page.getByTestId('preview-summary')
  await expect(previewSummary).toContainText('2 new')
  await expect(previewSummary).toContainText('0 duplicates')

  await page.getByRole('button', { name: 'Commit import' }).click()

  const importStatus = page
    .getByRole('status')
    .filter({ hasText: 'Imported statement.ofx' })
  await expect(importStatus).toContainText(
    '2 imported · 0 duplicates · 0 auto-categorized',
  )

  // --- 2. CATEGORIZE the debit into Wants: Dining Out ---------------------
  await nav(page).getByRole('link', { name: 'Transactions' }).click()
  await expect(page.getByRole('heading', { name: 'Transactions' })).toBeVisible()

  const coffeeRow = page.getByRole('row').filter({ hasText: 'Coffee Shop' })
  const coffeeCategory = coffeeRow.getByRole('combobox')
  await expect(coffeeCategory).toHaveValue('') // starts uncategorized
  await coffeeCategory.selectOption({ label: 'Wants: Dining Out' })

  // Wait until the categorize round-trips (transactions refetch shows a
  // non-empty category) so the budget query below sees the committed activity.
  await expect(coffeeCategory).not.toHaveValue('')

  // --- 3. BUDGET: verify income drives RTA, then assign ------------------
  await nav(page).getByRole('link', { name: 'Budget' }).click()
  await expect(page.getByRole('heading', { name: 'Budget' })).toBeVisible()

  // Income of $1,500 is the only money in the budget; nothing assigned yet.
  await expect(page.getByTestId('rta-amount')).toHaveText('$1,500.00')

  // Assign $50 to Dining Out via the inline editable cell.
  await page.getByRole('button', { name: 'Assigned for Dining Out' }).click()
  await page.getByLabel('Assigned for Dining Out').fill('50')
  await page.keyboard.press('Enter')

  // Assigning $50 reduces RTA to $1,450; spending the $42.50 did NOT.
  await expect(page.getByTestId('rta-amount')).toHaveText('$1,450.00')

  // Dining Out Available = assigned 50.00 + activity -42.50 = $7.50.
  const diningRow = page.getByRole('row').filter({ hasText: 'Dining Out' })
  await expect(diningRow).toContainText('$7.50')

  // --- 4. RE-IMPORT the same file → duplicates reported -----------------
  await nav(page).getByRole('link', { name: 'Import', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Import', exact: true })).toBeVisible()

  await page.getByLabel('OFX or QFX file input').setInputFiles(OFX_FILE)

  // The preview flags the already-imported file and counts both txns as dupes.
  await expect(page.getByRole('alert')).toContainText('already been imported')
  await expect(previewSummary).toContainText('0 new')
  await expect(previewSummary).toContainText('2 duplicates')

  // Committing anyway is a no-op import: FITID dedup drops both rows.
  await page.getByRole('button', { name: 'Commit import' }).click()
  await expect(
    page.getByRole('status').filter({ hasText: 'Imported statement.ofx' }),
  ).toContainText('0 imported · 2 duplicates · 0 auto-categorized')

  // RTA is unchanged by the duplicate import.
  await nav(page).getByRole('link', { name: 'Budget' }).click()
  await expect(page.getByTestId('rta-amount')).toHaveText('$1,450.00')
})
