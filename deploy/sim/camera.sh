#!/bin/bash
# Virtual camera: publishes H.264 over RTSP to MediaMTX, with wall-clock time and
# frame index burned into every frame.
#
# SIM_CAMERA_SOURCE  empty = testsrc2 pattern; otherwise the host path of a video file,
#                    bind-mounted by Compose at /sim/source (looped forever)
# SIM_CAMERA_SIZE    WxH, default 1920x1080
# SIM_CAMERA_FPS     default 15
set -euo pipefail

SOURCE="${SIM_CAMERA_SOURCE:-}"
SIZE="${SIM_CAMERA_SIZE:-1920x1080}"
FPS="${SIM_CAMERA_FPS:-15}"
TARGET="rtsp://mediamtx:8554/street"
MOUNTED_SOURCE=/sim/source
FONT=/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf

# NOTE: %F/%X keep ':' out of the strftime format, so only the function separator needs escaping.
# %3N is drawtext's millisecond extension to strftime; it makes latency readable from one screenshot.
OVERLAY="drawtext=fontfile=${FONT}:fontsize=h/18:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=12:x=24:y=24:text='%{localtime\:%F %X.%3N}  #%{n}'"

if [[ -z "$SOURCE" ]]; then
  input=(-re -f lavfi -i "testsrc2=size=${SIZE}:rate=${FPS}")
  filter="${OVERLAY},format=yuv420p"
else
  # NOTE: A silent fallback to the pattern would hide a misconfigured demo, so this is fatal.
  if [[ ! -f "$MOUNTED_SOURCE" || ! -r "$MOUNTED_SOURCE" ]]; then
    echo "sim-camera: SIM_CAMERA_SOURCE file not found or unreadable: ${SOURCE}" >&2
    exit 1
  fi
  input=(-stream_loop -1 -re -i "$MOUNTED_SOURCE")
  # NOTE: Files come in any geometry and rate; normalize so the stream matches the configured camera.
  filter="scale=${SIZE/x/:}:force_original_aspect_ratio=decrease,pad=${SIZE/x/:}:(ow-iw)/2:(oh-ih)/2,fps=${FPS},${OVERLAY},format=yuv420p"
fi

cmd=(
  ffmpeg -hide_banner -loglevel warning -nostdin
  "${input[@]}"
  -vf "$filter"
  -an
  -c:v libx264 -preset ultrafast -tune zerolatency
  -bf 0 -g "$FPS" -keyint_min "$FPS" -sc_threshold 0
  -f rtsp -rtsp_transport tcp "$TARGET"
)

echo "sim-camera: source=${SOURCE:-testsrc2} size=${SIZE} fps=${FPS} -> ${TARGET}"

# NOTE: bash defers signals while a foreground child runs, so `docker stop` would hang until
# SIGKILL. Run ffmpeg in the background and forward the stop to it instead.
ffmpeg_pid=
trap '[[ -n "$ffmpeg_pid" ]] && kill "$ffmpeg_pid" 2>/dev/null; exit 0' TERM INT

# NOTE: MediaMTX may be starting or restarting; keep republishing instead of exiting.
while true; do
  "${cmd[@]}" &
  ffmpeg_pid=$!
  wait "$ffmpeg_pid" || echo "sim-camera: ffmpeg exited with status $?, retrying in 1s" >&2
  ffmpeg_pid=
  sleep 1
done
