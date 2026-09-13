#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
audio=$(mktemp /tmp/agentteam-narration.XXXXXX.aiff)
trap 'rm -f "$audio"' EXIT
say -v Kyoko -r 210 -f scripts/video/real-walkthrough-ja.txt -o "$audio"
ffmpeg -y -i docs/media/replay-research.mp4 -i "$audio" \
  -vf 'tpad=stop_mode=clone:stop_duration=4' -t 32 \
  -c:v libx264 -crf 21 -pix_fmt yuv420p -c:a aac -b:a 128k \
  -movflags +faststart docs/media/real-walkthrough-ja.mp4
