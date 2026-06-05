function App() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-emerald-900 p-6">
      <div className="w-full max-w-md rounded-2xl bg-white/95 shadow-2xl ring-1 ring-black/5 p-10 text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100">
          <span className="text-3xl font-black text-emerald-600">$</span>
        </div>
        <h1 className="text-5xl font-extrabold tracking-tight text-slate-900">
          BUD
        </h1>
        <p className="mt-3 text-sm font-medium uppercase tracking-widest text-emerald-600">
          Phase 0 Scaffold
        </p>
        <p className="mt-4 text-slate-500">
          Vite + React + TypeScript + Tailwind placeholder. Real pages and the
          API client arrive in later phases.
        </p>
        <div className="mt-8 inline-flex items-center gap-2 rounded-full bg-slate-100 px-4 py-1.5 text-xs font-medium text-slate-600">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          Tailwind styling active
        </div>
      </div>
    </div>
  )
}

export default App
