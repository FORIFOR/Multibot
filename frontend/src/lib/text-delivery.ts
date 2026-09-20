/** Encode requester-owned literal exclusions in standard JSON Schema.
 * The execution layer, shared with API/CLI callers, validates actual file bytes.
 */
export function textDeliverySchema(min: number | undefined, max: number | undefined, excluded: string) {
  const phrases = [...new Set(excluded.split(/\r?\n/).map(line => line.trim()).filter(Boolean))]
  // Escape only regex metacharacters, using the common ECMA/Python subset.
  const literal = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return {
    type: 'string',
    ...(min !== undefined ? { minLength: min } : {}),
    ...(max !== undefined ? { maxLength: max } : {}),
    ...(phrases.length ? { not: { anyOf: phrases.map(phrase => ({ pattern: literal(phrase) })) } } : {}),
  }
}
