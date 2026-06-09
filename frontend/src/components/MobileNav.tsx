import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'

type NavSection = {
  readonly to: string
  readonly label: string
  readonly end?: boolean
}

/**
 * Mobile-only navigation. Renders a hamburger button (visible below the `md`
 * breakpoint, the inverse of the desktop sidebar's `hidden md:flex`) that opens
 * a drawer containing the same nav links as the desktop sidebar.
 *
 * The route list is passed in from AppShell so desktop and mobile render from a
 * single source — no route definitions are duplicated here.
 *
 * The drawer closes on navigation (link tap), backdrop click, the close button,
 * and the Escape key.
 */
export default function MobileNav({
  sections,
}: {
  sections: readonly NavSection[]
}) {
  const [open, setOpen] = useState(false)

  // Dismiss with the Escape key while the drawer is open.
  useEffect(() => {
    if (!open) return
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open])

  return (
    <div className="md:hidden">
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open navigation menu"
        aria-expanded={open}
        className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
      >
        {/* Hamburger icon */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
          className="h-6 w-6"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3.75 6.75h16.5M3.75 12h16.5M3.75 17.25h16.5"
          />
        </svg>
      </button>

      {open && (
        <div className="fixed inset-0 z-50">
          {/* Backdrop */}
          <button
            type="button"
            aria-label="Close navigation menu"
            onClick={() => setOpen(false)}
            className="absolute inset-0 bg-slate-900/40"
          />

          {/* Drawer */}
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Main navigation"
            className="absolute inset-y-0 left-0 flex w-64 max-w-[80%] flex-col border-r border-slate-200 bg-white shadow-xl"
          >
            <div className="flex items-center justify-between px-5 py-4">
              <span className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-100 text-base font-black text-emerald-600">
                  $
                </span>
                <span className="text-lg font-extrabold tracking-tight text-slate-900">
                  BUD
                </span>
              </span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close navigation menu"
                className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                  className="h-5 w-5"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6 18 18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <nav
              aria-label="Mobile navigation"
              className="flex flex-1 flex-col gap-1 px-3 py-2"
            >
              {sections.map((section) => (
                <NavLink
                  key={section.to}
                  to={section.to}
                  end={section.end ?? false}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    [
                      'rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                    ].join(' ')
                  }
                >
                  {section.label}
                </NavLink>
              ))}
            </nav>
          </div>
        </div>
      )}
    </div>
  )
}
