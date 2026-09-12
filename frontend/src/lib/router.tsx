import { useEffect, useState } from 'react'

export function usePath(): [string, (p: string) => void] {
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  const nav = (p: string) => { window.history.pushState({}, '', p); setPath(p) }
  return [path, nav]
}

export function Link({ to, nav, className, children }: { to: string; nav: (p: string) => void; className?: string; children: React.ReactNode }) {
  return <a href={to} className={className} onClick={(e) => { if (e.metaKey || e.ctrlKey) return; e.preventDefault(); nav(to) }}>{children}</a>
}
