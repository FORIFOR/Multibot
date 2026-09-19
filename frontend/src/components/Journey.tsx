import { getLang } from '../lib/i18n'
import type { JourneyPanel } from '../lib/journey'
export default function Journey({ current, onSelect }: { current: JourneyPanel; onSelect?: (panel: JourneyPanel) => void }) {
  const en = getLang() === 'en'
  const steps: [JourneyPanel, string][] = [['request', en ? 'Ask' : 'お願いする'], ['team', en ? 'Meet the team' : 'チームを見る'], ['results', en ? 'See results' : 'できたものを見る']]
  return <nav className="journey" aria-label={en ? 'Your work in three steps' : 'お仕事の3ステップ'}>
    <ol>{steps.map(([id, label], index) => <li key={id} aria-current={id === current ? 'step' : undefined}>
      {onSelect ? <button type="button" data-journey={id} onClick={() => onSelect(id)} aria-pressed={id === current}><span className="step-number" aria-hidden="true">{index + 1}</span><span>{label}</span></button>
        : <span className="journey-static"><span className="step-number" aria-hidden="true">{index + 1}</span><span>{label}</span></span>}
    </li>)}</ol>
  </nav>
}
