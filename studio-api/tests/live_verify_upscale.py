"""Live verification test for MAGI upscaling."""
import sys
sys.path.insert(0, r'C:\AdeptFilmWorks\AIVideoStudio\studio-api')

from app.magi.upscaling import upscale_frame, _parse_resolution
from pathlib import Path
import subprocess
import json

src = r'C:\AdeptFilmWorks\AIVideoStudio\studio-api\tests\fixtures\magi_test_720p.mp4'

# Test 1: FFmpeg Lanczos upscale to 1080p
out = r'C:\AdeptFilmWorks\AIVideoStudio\studio-api\tests\fixtures\magi_test_1080p.mp4'
result = upscale_frame(src, out, engine="ffmpeg-scale", model="lanczos", target_width=1920, target_height=1080)
print("Output:", result)
assert Path(result).is_file(), "Output file not created"
size = Path(result).stat().st_size
print("Output size:", size, "bytes")
assert size > 1000, "Output too small"

# Verify resolution
probe = subprocess.run([
    'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', result
], capture_output=True, text=True)
info = json.loads(probe.stdout)
video_stream = next(s for s in info["streams"] if s["codec_type"] == "video")
width = int(video_stream["width"])
height = int(video_stream["height"])
print(f"Output resolution: {width}x{height}")
assert width == 1920, f"Expected width 1920, got {width}"
assert height == 1080, f"Expected height 1080, got {height}"
print("PASS: Resolution correct")

# Verify duration preserved
probe_src = subprocess.run([
    'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', src
], capture_output=True, text=True)
src_info = json.loads(probe_src.stdout)
src_dur = float(src_info["format"]["duration"])
probe_out = subprocess.run([
    'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', result
], capture_output=True, text=True)
out_info = json.loads(probe_out.stdout)
out_dur = float(out_info["format"]["duration"])
print(f"Source duration: {src_dur:.2f}s, Output duration: {out_dur:.2f}s")
assert abs(out_dur - src_dur) < 0.5, f"Duration mismatch: {src_dur} vs {out_dur}"
print("PASS: Duration preserved")

# Verify audio stream exists
audio_streams = [s for s in info["streams"] if s["codec_type"] == "audio"]
assert len(audio_streams) > 0, "No audio stream in output"
print(f"PASS: Audio preserved (codec: {audio_streams[0].get('codec_name', 'unknown')})")

# Verify frame rate preserved
fps_str = video_stream.get("r_frame_rate", "24/1")
num, den = fps_str.split("/")
fps = float(num) / float(den)
print(f"Output frame rate: {fps:.2f}")
assert abs(fps - 24) < 1, f"Frame rate mismatch: {fps} vs 24"
print("PASS: Frame rate preserved")

print("\nALL UPSCALE LIVE TESTS PASSED")
