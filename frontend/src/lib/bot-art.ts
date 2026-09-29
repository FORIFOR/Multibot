// Kept apart from bot-presentation.ts so that module stays importable by the Node unit tests (no asset imports).
import type { BotKind } from './bot-presentation'
/** Original default characters (assets/bots/*.svg), shown when the user has not chosen an emoji.
 *  The same files are inlined by the public site (docs/site/build_site.py), so the two cannot drift. */
import masterArt from '../assets/bots/master.svg'
import researcherArt from '../assets/bots/researcher.svg'
import builderArt from '../assets/bots/builder.svg'
import reviewerArt from '../assets/bots/reviewer.svg'
import reporterArt from '../assets/bots/reporter.svg'
import helperArt from '../assets/bots/helper.svg'
const ART: Record<BotKind, string> = { master: masterArt, researcher: researcherArt, builder: builderArt, reviewer: reviewerArt, reporter: reporterArt, helper: helperArt }
export function botArt(kind: BotKind): string { return ART[kind] }
