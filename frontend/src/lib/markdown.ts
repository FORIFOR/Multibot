/** A small Markdown parser for deliverables and summaries. It produces plain data (no HTML), so a renderer can only
 *  ever create text, emphasis, code, lists, tables and http(s) links. Raw HTML in the source stays text, and syntax it
 *  does not understand is kept as written, so nothing in a deliverable is silently dropped. */
export type Inline = { t: 'text' | 'strong' | 'code'; v: string } | { t: 'link'; v: string; href: string }
export type Block =
  | { t: 'h'; level: number; c: Inline[] } | { t: 'p'; lines: Inline[][] } | { t: 'ul' | 'ol'; items: Inline[][] }
  | { t: 'pre'; v: string } | { t: 'hr' } | { t: 'quote'; c: Inline[] } | { t: 'table'; head: Inline[][]; rows: Inline[][][] }

const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[[^\]\n]+\]\(https?:\/\/[^\s)]+\)|https?:\/\/[^\s<>)）」』、。]+)/g
export function parseInline(text: string): Inline[] {
  return text.split(INLINE).filter(Boolean).map((part): Inline => {
    if (part.startsWith('**') && part.length > 4) return { t: 'strong', v: part.slice(2, -2) }
    if (part.startsWith('`') && part.length > 2) return { t: 'code', v: part.slice(1, -1) }
    const link = /^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/.exec(part)
    if (link) return { t: 'link', v: link[1], href: link[2] }
    if (/^https?:\/\//.test(part)) return { t: 'link', v: part, href: part }
    return { t: 'text', v: part }
  })
}
const cells = (line: string) => line.trim().replace(/^\||\|$/g, '').split('|').map(c => parseInline(c.trim()))
const ITEM = /^([-*+]|\d+[.)])\s+(.*)$/

export function parseMarkdown(source: string): Block[] {
  // A summary flattened onto one line still carries " ## " heading markers; restore those breaks.
  const lines = (source.includes('\n') ? source : source.replace(/\s+(#{1,6}\s)/g, '\n$1')).replace(/\r\n?/g, '\n').split('\n')
  const out: Block[] = []
  let i = 0
  while (i < lines.length) {
    const trimmed = lines[i].trim()
    if (!trimmed) { i++; continue }
    const fence = /^(```|~~~)/.exec(trimmed)
    if (fence) {
      const body: string[] = []; i++
      while (i < lines.length && !lines[i].trim().startsWith(fence[1])) body.push(lines[i++])
      i++; out.push({ t: 'pre', v: body.join('\n') }); continue
    }
    const head = /^(#{1,6})\s+(.*)$/.exec(trimmed)
    if (head) { out.push({ t: 'h', level: head[1].length, c: parseInline(head[2]) }); i++; continue }
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) { out.push({ t: 'hr' }); i++; continue }
    if (trimmed.startsWith('|') && i + 1 < lines.length && /^\|?\s*:?-{2,}/.test(lines[i + 1].trim())) {
      const headRow = cells(trimmed); i += 2; const rows: Inline[][][] = []
      while (i < lines.length && lines[i].trim().startsWith('|')) rows.push(cells(lines[i++]))
      out.push({ t: 'table', head: headRow, rows }); continue
    }
    const first = ITEM.exec(trimmed)
    if (first) {
      const ordered = /^\d/.test(first[1]); const items: Inline[][] = []
      while (i < lines.length) { const m = ITEM.exec(lines[i].trim()); if (!m || /^\d/.test(m[1]) !== ordered) break; items.push(parseInline(m[2])); i++ }
      out.push({ t: ordered ? 'ol' : 'ul', items }); continue
    }
    if (trimmed.startsWith('>')) {
      const quote: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('>')) quote.push(lines[i++].trim().replace(/^>\s?/, ''))
      out.push({ t: 'quote', c: parseInline(quote.join(' ')) }); continue
    }
    const para: Inline[][] = []
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|```|~~~|[-*+]\s|\d+[.)]\s|>|\|)/.test(lines[i].trim())) para.push(parseInline(lines[i++].trim()))
    if (!para.length) { para.push(parseInline(trimmed)); i++ }
    out.push({ t: 'p', lines: para })
  }
  return out
}
