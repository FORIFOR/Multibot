import { useEffect, useState } from 'react'
import type { RunDetail, Event } from '../lib/api'
import { getLang } from '../lib/i18n'
import { isSettled } from '../lib/journey'

export default function ElapsedTime({ run, events }: { run: RunDetail; events: Event[] }) {
  const en = getLang() === 'en'
  const ticking = run.live && !isSettled(run.status) && !run.finished_at
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    if (!ticking) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [ticking])
  const start = run.started_at ? Date.parse(run.started_at) : NaN
  // Start-to-end elapsed time includes approval waits and any pause before resuming.
  // Without an end record, show only the duration covered by the last real event.
  const stop = isSettled(run.status) ? events.findLast(e => ['run.interrupted','run.cancelled','run.failed','run.partial','run.completed','run.blocked'].includes(e.type)) : undefined
  const end = run.finished_at ? Date.parse(run.finished_at) : ticking ? now : Date.parse(stop?.recorded_at || events.at(-1)?.recorded_at || '')
  const seconds = Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, Math.floor((end - start) / 1000)) : null
  const duration = seconds === null ? '—' : `${Math.floor(seconds / 3600) > 0 ? `${Math.floor(seconds / 3600)}:` : ''}${String(Math.floor(seconds / 60) % 60).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
  const recorded = !run.finished_at && !ticking && seconds !== null
  return <span className="conversation-elapsed" title={en ? 'Time since the first start, including approval and pause time. Without an end record, measured to the stop record, or the last event if none exists.' : '最初の開始からの経過時間です。承認待ち・中断時間を含みます。終了時刻がない場合は停止記録まで、停止記録もない場合は最後の記録までを表示します。'}>
    {recorded ? (en ? 'Recorded' : '記録時点') : (en ? 'Elapsed' : '経過')} <time dateTime={seconds === null ? undefined : `PT${seconds}S`}>{duration}</time>
  </span>
}
