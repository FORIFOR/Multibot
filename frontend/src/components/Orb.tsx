/** Small CSS activity mark. No GPU/iframe work: motion preferences and the
 * workroom's pause-animation control can stop every visible animation. */
export type OrbState = 'idle' | 'thinking'
export default function Orb({ state, size = 44, title }: { state: OrbState; size?: number; title?: string }) {
  return <span className="activity-mark" role="img" aria-label={title || state}
    title={title} style={{ width: Math.min(size, 44), height: Math.min(size, 44), display: 'inline-grid', placeItems: 'center' }}>
    <span className="pulse" aria-hidden="true" style={state === 'idle' ? { animation: 'none' } : undefined} />
  </span>
}
