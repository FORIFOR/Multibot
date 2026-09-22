// Cuts the raw recording into the site (16:9) and X (9:16) versions. Same source, different layout and captions;
// the vertical version re-places the UI and the captions instead of cropping the middle out.
//   node frontend/scripts/edit-demo.mjs <raw.webm> <capDir> <outDir> [ja|en]
import { execFileSync } from 'node:child_process'
import { mkdirSync, rmSync } from 'node:fs'
const [raw, capDir, outDir, lang = 'ja'] = process.argv.slice(2)
const tmp = `${outDir}/parts`
rmSync(tmp, { recursive: true, force: true }); mkdirSync(tmp, { recursive: true })
const ff = (args) => execFileSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', ...args], { stdio: 'inherit' })

// from timeline.json of the recorded run. Each language has its own recording, so the cuts differ.
const EN = process.env.DEMO_CUT === 'en'
const segments = EN ? [
  { name: 's1', from: 902.0, to: 905.1, speed: 1.0, cap: 'en-1', focus: [40, 860], wide: [20, 90, 1000, 625] },
  { name: 's2', from: 1.6, to: 6.3, speed: 1.2, cap: 'en-2', focus: [260, 860] },
  { name: 's3', from: 6.3, to: 10.7, speed: 1.4, cap: 'en-3', focus: [260, 860] },
  { name: 's4', from: 10.7, to: 13.6, speed: 1.0, cap: 'en-4', focus: [260, 860] },
  { name: 's5', from: 15.3, to: 890.0, speed: 175.0, cap: 'en-5', focus: [20, 860] },
  { name: 's6', from: 894.0, to: 905.1, speed: 1.4, cap: 'en-6', focus: [40, 860], wide: [20, 90, 1000, 625] },
] : [
  { name: 's1', from: 816.0, to: 819.2, speed: 1.0, cap: `${lang}-1`, focus: [40, 860], wide: [20, 90, 1000, 625] },
  { name: 's2', from: 1.5, to: 4.7, speed: 1.0, cap: `${lang}-2`, focus: [260, 860] },
  { name: 's3', from: 4.7, to: 9.1, speed: 1.4, cap: `${lang}-3`, focus: [260, 860] },
  { name: 's4', from: 9.1, to: 12.0, speed: 1.0, cap: `${lang}-4`, focus: [260, 860] },
  { name: 's5', from: 13.7, to: 800.0, speed: 160.0, cap: `${lang}-5`, focus: [20, 860] },
  { name: 's6', from: 808.0, to: 819.2, speed: 1.4, cap: `${lang}-6`, focus: [40, 860], wide: [20, 90, 1000, 625] },
]

// 16:9 for the site
for (const s of segments) {
  const wide = s.wide ? `crop=${s.wide[2]}:${s.wide[3]}:${s.wide[0]}:${s.wide[1]},scale=1280:800` : 'scale=1280:800'
  ff(['-ss', String(s.from), '-to', String(s.to), '-i', raw, '-i', `${capDir}/${s.cap}.png`,
      '-filter_complex', `[0:v]setpts=PTS/${s.speed},${wide},fps=30[v];[1:v]scale=1280:-1[c];[v][c]overlay=0:H-h[o]`,
      '-map', '[o]', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '22', '-pix_fmt', 'yuv420p', `${tmp}/${s.name}.mp4`])
}
ff(['-loop', '1', '-t', '3', '-i', `${capDir}/card-${lang}.png`, '-vf', 'scale=1280:800,fps=30',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '22', '-pix_fmt', 'yuv420p', `${tmp}/s7.mp4`])
execFileSync('bash', ['-c', `printf "file '%s'\\n" ${tmp}/s1.mp4 ${tmp}/s2.mp4 ${tmp}/s3.mp4 ${tmp}/s4.mp4 ${tmp}/s5.mp4 ${tmp}/s6.mp4 ${tmp}/s7.mp4 > ${tmp}/list.txt`])
ff(['-f', 'concat', '-safe', '0', '-i', `${tmp}/list.txt`, '-c:v', 'libx264', '-preset', 'slow', '-crf', '23',
    '-movflags', '+faststart', '-pix_fmt', 'yuv420p', `${outDir}/demo-site.mp4`])

// 9:16 for X: crop to the part of the screen that is actually doing something and enlarge it, so the UI stays
// readable on a phone, then give the caption its own band. Not a centre crop of the whole desktop frame.
for (const s of segments) {
  const [cx, cw] = s.focus   // where the action is in the 1280x800 frame
  ff(['-ss', String(s.from), '-to', String(s.to), '-i', raw, '-i', `${capDir}/${s.cap}-v.png`,
      '-filter_complex',
      `color=c=0xf5f5f5:s=1080x1920:r=30[bg];` +
      `[0:v]setpts=PTS/${s.speed},crop=${cw}:800:${cx}:0,scale=1080:-2,fps=30[v];` +
      `[bg][v]overlay=0:300:shortest=1[base];` +
      `[1:v]scale=1080:-1[c];[base][c]overlay=0:H-h-90[o]`,
      '-map', '[o]', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '22', '-pix_fmt', 'yuv420p', `${tmp}/v-${s.name}.mp4`])
}
ff(['-loop', '1', '-t', '3', '-i', `${capDir}/card-${lang}-v.png`, '-vf', 'scale=1080:1920,fps=30',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '22', '-pix_fmt', 'yuv420p', `${tmp}/v-s7.mp4`])
execFileSync('bash', ['-c', `printf "file '%s'\\n" ${tmp}/v-s1.mp4 ${tmp}/v-s2.mp4 ${tmp}/v-s3.mp4 ${tmp}/v-s4.mp4 ${tmp}/v-s5.mp4 ${tmp}/v-s6.mp4 ${tmp}/v-s7.mp4 > ${tmp}/vlist.txt`])
ff(['-f', 'concat', '-safe', '0', '-i', `${tmp}/vlist.txt`, '-c:v', 'libx264', '-preset', 'slow', '-crf', '23',
    '-movflags', '+faststart', '-pix_fmt', 'yuv420p', `${outDir}/demo-x.mp4`])

// poster: the frame where the outcome is on screen
ff(['-ss', '352.4', '-i', raw, '-frames:v', '1', '-q:v', '3', `${outDir}/demo-poster.jpg`])
console.log('built', outDir)
