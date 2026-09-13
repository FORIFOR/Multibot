// Liquid-glass "thinking" orb, shown while a model call is in flight.
// The orb page is a standalone export from the MIT-licensed Liquid Orb Editor (https://github.com/LerSent001/orb),
// generated with the parameter snapshot in src/assets/orb-params.txt and vendored as src/assets/orb.html.
// It runs inside a same-origin srcdoc iframe (no network, WebGPU) and is driven through window.liquidOrb.setState.
// Browsers without WebGPU get the plain pulse dot instead, so nothing here is on the critical path.
import { useEffect, useRef, useState } from 'react'
import orbHtml from '../assets/orb.html?raw'

export type OrbState = 'idle' | 'thinking'

let gpuProbe: Promise<boolean> | null = null
/** True once a WebGPU adapter actually answers (headless or software-only browsers say no). Cached per page. */
export function webGPUAvailable(): Promise<boolean> {
  if (!gpuProbe) {
    gpuProbe = (async () => {
      try {
        const gpu = (navigator as any).gpu
        if (!gpu) return false
        const adapter = await gpu.requestAdapter()
        return !!adapter
      } catch {
        return false
      }
    })()
  }
  return gpuProbe
}

export default function Orb({ state, size = 64, title }: { state: OrbState; size?: number; title?: string }) {
  const ref = useRef<HTMLIFrameElement>(null)
  const [ok, setOk] = useState<boolean | null>(null)
  useEffect(() => { let alive = true; webGPUAvailable().then((v) => { if (alive) setOk(v) }); return () => { alive = false } }, [])
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const apply = () => {
      try { (el.contentWindow as any)?.liquidOrb?.setState(state) } catch { /* not ready yet */ }
    }
    apply()
    el.addEventListener('load', apply)
    return () => el.removeEventListener('load', apply)
  }, [state, ok])
  if (!ok) return <span className="pulse" title={title} />
  return (
    <iframe ref={ref} className="orb" title={title || 'thinking'} aria-hidden="true" tabIndex={-1}
            srcDoc={orbHtml} sandbox="allow-scripts allow-same-origin" scrolling="no"
            style={{ width: size, height: size }} />
  )
}
