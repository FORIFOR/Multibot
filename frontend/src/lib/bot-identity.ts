/** Emoji identity is plain text, never HTML. Accept one complete grapheme. */
export function isBotEmoji(input: string): boolean {
  const value = input.trim()
  if (!value || Array.from(value).length > 16) return false
  const segments = [...new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(value)]
  return segments.length === 1 && /\p{Extended_Pictographic}|\p{Regional_Indicator}|\u20e3/u.test(value)
}
export function newBotId(): string {
  return 'bot-' + crypto.randomUUID().replace(/-/g, '').slice(0, 12)
}
export const EMOJI_CHOICES = [
  ['🦊', 'きつね', 'Fox'], ['🐼', 'パンダ', 'Panda'], ['🐰', 'うさぎ', 'Rabbit'],
  ['🐱', 'ねこ', 'Cat'], ['🐶', 'いぬ', 'Dog'], ['🦉', 'ふくろう', 'Owl'],
  ['🐙', 'たこ', 'Octopus'], ['🌱', '芽', 'Seedling'], ['🚀', 'ロケット', 'Rocket'],
  ['🎨', 'パレット', 'Palette'], ['🔬', '顕微鏡', 'Microscope'], ['💡', '電球', 'Light bulb'],
] as const
