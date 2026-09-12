#!/bin/sh
# Rebuilds docs/media/intro.mp4: title cards (scenes.html → PNG via headless Chrome), the raw walkthrough
# recording (frontend/scripts/record-demo.mjs against the fake demo server), synthesized Japanese narration
# (macOS `say -v Kyoko`), lower-third captions and a ducked BGM track. Every step is disclosed on screen.
#   BGM="/path/to/track.wav" REC=/tmp/agentteam-demo/*.webm sh scripts/video/build-intro.sh
set -eu
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd); W=${WORK:-/tmp/agentteam-promo}
BGM=${BGM:?set BGM=/path/to/track.wav}; REC=${REC:?set REC=/path/to/recording.webm}
mkdir -p "$W/cards" "$W/vo"; cp "$HERE/scenes.html" "$W/cards/"
cat > "$W/cards.mjs" <<JS
import { chromium } from 'playwright-core'
const b = await chromium.launch({ channel: 'chrome', headless: true }); const p = await b.newPage({ viewport: { width: 1280, height: 720 } })
await p.goto('file://$W/cards/scenes.html', { waitUntil: 'networkidle' }); await p.waitForTimeout(1200)
for (const id of ['c1','c2','c3']) await p.locator('#'+id).screenshot({ path: '$W/cards/'+id+'.png' })
for (const id of ['l1','l2','l3','l4','l5']) await p.locator('#'+id).screenshot({ path: '$W/cards/'+id+'.png', omitBackground: true })
await b.close()
JS
(cd "$ROOT/frontend" && cp "$W/cards.mjs" scripts/_cards.mjs && node scripts/_cards.mjs && rm scripts/_cards.mjs)
while IFS='|' read -r id text; do say -v Kyoko -r 185 -o "$W/vo/$id.aiff" "$text"; ffmpeg -y -v error -i "$W/vo/$id.aiff" -ar 48000 -ac 2 -af "loudnorm=I=-16:TP=-1.5:LRA=7" "$W/vo/$id.wav"; done < "$HERE/narration.txt"
cd "$W"
ffmpeg -y -v error -loop 1 -framerate 30 -t 6.5 -i cards/c1.png -vf "fade=t=in:st=0:d=0.6,fade=t=out:st=6.0:d=0.5,format=yuv420p" -c:v libx264 -crf 20 -r 30 seg1.mp4
ffmpeg -y -v error -loop 1 -framerate 30 -t 8.5 -i cards/c2.png -vf "fade=t=in:st=0:d=0.5,fade=t=out:st=8.0:d=0.5,format=yuv420p" -c:v libx264 -crf 20 -r 30 seg2.mp4
ffmpeg -y -v error -i "$REC" -i cards/l1.png -i cards/l2.png -i cards/l3.png -i cards/l4.png -i cards/l5.png -filter_complex "[0:v]scale=1280:720,fps=30,format=yuv420p[v0];[v0][1:v]overlay=0:0:enable='between(t,1,8.5)'[v1];[v1][2:v]overlay=0:0:enable='between(t,9.5,17.5)'[v2];[v2][3:v]overlay=0:0:enable='between(t,18.5,21.5)'[v3];[v3][4:v]overlay=0:0:enable='between(t,29,34.5)'[v4];[v4][5:v]overlay=0:0:enable='between(t,35,37.2)',fade=t=in:st=0:d=0.4,fade=t=out:st=36.7:d=0.5[vo]" -map "[vo]" -c:v libx264 -crf 20 -r 30 -an seg3.mp4
ffmpeg -y -v error -loop 1 -framerate 30 -t 6 -i cards/c3.png -vf "fade=t=in:st=0:d=0.5,fade=t=out:st=5.2:d=0.8,format=yuv420p" -c:v libx264 -crf 20 -r 30 seg4.mp4
printf "file 'seg1.mp4'\nfile 'seg2.mp4'\nfile 'seg3.mp4'\nfile 'seg4.mp4'\n" > list.txt; ffmpeg -y -v error -f concat -safe 0 -i list.txt -c copy video_noaudio.mp4
ffmpeg -y -v error -i video_noaudio.mp4 -i "$BGM" -i vo/n1.wav -i vo/n2.wav -i vo/n3.wav -i vo/n4.wav -i vo/n5.wav -i vo/n6.wav -i vo/n7.wav -filter_complex "[2:a]adelay=400|400[a1];[3:a]adelay=6900|6900[a2];[4:a]adelay=24000|24000[a3];[5:a]adelay=33500|33500[a4];[6:a]adelay=44000|44000[a5];[7:a]adelay=50000|50000[a6];[8:a]adelay=52600|52600[a7];[a1][a2][a3][a4][a5][a6][a7]amix=inputs=7:normalize=0:dropout_transition=0,apad=whole_dur=58.3,asplit=2[vo1][vo2];[1:a]atrim=0:58.3,afade=t=in:st=0:d=1.5,afade=t=out:st=55.5:d=2.8,volume=-13dB[bgm];[bgm][vo1]sidechaincompress=threshold=0.05:ratio=6:attack=40:release=500:makeup=1[duck];[duck][vo2]amix=inputs=2:normalize=0[mix];[mix]loudnorm=I=-16:TP=-1.5:LRA=9[aout]" -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 160k -t 58.23 "$ROOT/docs/media/intro.mp4"
echo "wrote $ROOT/docs/media/intro.mp4"
