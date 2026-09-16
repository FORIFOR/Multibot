import { useEffect, useState } from 'react'

const currentPath = () => window.location.pathname + window.location.search + window.location.hash

// Query parameters select a view; they are never part of a run identifier.
export function getRunId(path: string): string | null {
  return path.match(/^\/runs\/([^/?#]+)/)?.[1] ?? null
}

export function usePath(): [string, (p: string) => void] {
  const [path, setPath] = useState(currentPath())
  useEffect(() => {
    const onPop = () => setPath(currentPath())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  const nav = (p: string) => { window.history.pushState({}, '', p); setPath(currentPath()) }
  return [path, nav]
}

export function Link({ to, nav, className, children }: { to: string; nav: (p: string) => void; className?: string; children: React.ReactNode }) {
  return <a href={to} className={className} onClick={(e) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
    e.preventDefault()
    nav(to)
  }}>{children}</a>
}
