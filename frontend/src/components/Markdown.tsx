import type { ReactNode } from 'react'
import { parseMarkdown, type Inline } from '../lib/markdown'

const inline = (parts: Inline[]): ReactNode[] => parts.map((p, i) =>
  p.t === 'strong' ? <strong key={i}>{p.v}</strong> : p.t === 'code' ? <code key={i}>{p.v}</code>
    : p.t === 'link' ? <a key={i} href={p.href} target="_blank" rel="noreferrer noopener">{p.v}</a> : p.v)

/** Renders parsed Markdown as React elements only; see lib/markdown.ts for what can and cannot appear. */
export default function Markdown({ text, className = 'md' }: { text: string; className?: string }) {
  return <div className={className}>{parseMarkdown(text).map((b, k) => {
    switch (b.t) {
      case 'h': { const H = (['h2', 'h3', 'h4', 'h5', 'h6', 'h6'] as const)[b.level - 1]; return <H key={k}>{inline(b.c)}</H> }
      case 'p': return <p key={k}>{b.lines.flatMap((line, n) => (n ? [<br key={'b' + n} />, ...inline(line)] : inline(line)))}</p>
      case 'ul': return <ul key={k}>{b.items.map((it, n) => <li key={n}>{inline(it)}</li>)}</ul>
      case 'ol': return <ol key={k}>{b.items.map((it, n) => <li key={n}>{inline(it)}</li>)}</ol>
      case 'pre': return <pre key={k}><code>{b.v}</code></pre>
      case 'hr': return <hr key={k} />
      case 'quote': return <blockquote key={k}>{inline(b.c)}</blockquote>
      case 'table': return <div className="md-table" key={k}><table><thead><tr>{b.head.map((c, n) => <th key={n}>{inline(c)}</th>)}</tr></thead>
        <tbody>{b.rows.map((r, n) => <tr key={n}>{r.map((c, m) => <td key={m}>{inline(c)}</td>)}</tr>)}</tbody></table></div>
    }
  })}</div>
}
