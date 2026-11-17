import { Outlet } from "react-router-dom";

export function Layout() {
  return (
    <div className="mx-auto min-h-screen max-w-7xl px-3 py-4">
      <header className="mb-4 flex items-center gap-3 border-b border-slate-800 pb-3">
        <h1 className="text-lg font-semibold">hablator</h1>
        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
          debug console
        </span>
      </header>
      <Outlet />
    </div>
  );
}
