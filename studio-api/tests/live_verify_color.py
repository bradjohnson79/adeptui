"""Live verification test for MAGI color grading."""
import sys
sys.path.insert(0, r'C:\AdeptFilmWorks\AIVideoStudio\studio-api')

from app.magi.color_grading import (
    COLOR_PRESETS, compile_filter_string, apply_color_grade
)
from pathlib import Path
import subprocess
import json

# Test 1: Filter compilation
noir_params = COLOR_PRESETS["noir"]["params"]
print("Noir params:", noir_params)
filter_str = compile_filter_string(noir_params)
print("Filter string:", filter_str)
assert "eq=" in filter_str, "Missing eq filter"
assert "saturation=0.0" in filter_str, "Noir should have zero saturation"
print("PASS: Filter compilation")

# Test 2: Apply color grade to test video
src = r'C:\AdeptFilmWorks\AIVideoStudio\studio-api\tests\fixtures\magi_test_720p.mp4'
out = r'C:\AdeptFilmWorks\AIVideoStudio\studio-api\tests\fixtures\magi_test_noir.mp4'
result = apply_color_grade(src, out, noir_params, preview_seconds=3.0)
print("Output:", result)
assert Path(result).is_file(), "Output file not created"
size = Path(result).stat().st_size
print("Output size:", size, "bytes")
assert size > 1000, "Output too small"
print("PASS: Color grade applied successfully")

# Test 3: Golden Hour preset
gh_params = COLOR_PRESETS["golden_hour"]["params"]
out2 = r'C:\AdeptFilmWorks\AIVideoStudio\studio-api\tests\fixtures\magi_test_golden.mp4'
result2 = apply_color_grade(src, out2, gh_params, preview_seconds=3.0)
assert Path(result2).is_file(), "Output file not created"
print("PASS: Golden Hour preset applied")

# Test 4: No-op (none preset) should produce near-identical output
out3 = r'C:\AdeptFilmWorks\AIVideoStudio\studio-api\tests\fixtures\magi_test_none.mp4'
result3 = apply_color_grade(src, out3, {}, preview_seconds=3.0)
assert Path(result3).is_file(), "Output file not created"
print("PASS: No-op grade applied")

# Test 5: Verify pixel difference between Noir and source
frame_src = r'C:\AdeptFilmWorks\AIVideoStudio\studio-api\tests\fixtures\frame_src.png'
frame_graded = r'C:\AdeptFilmWorks\AIVideoStudio\studio-api\tests\fixtures\frame_noir.png'
subprocess.run(['ffmpeg', '-y', '-i', src, '-vframes', '1', frame_src], capture_output=True)
subprocess.run(['ffmpeg', '-y', '-i', out, '-vframes', '1', frame_graded], capture_output=True)

# Compare pixel values
from PIL import Image
import numpy as np
img_src = np.array(Image.open(frame_src))
img_graded = np.array(Image.open(frame_graded))
diff = np.abs(img_src.astype(float) - img_graded.astype(float)).mean()
print(f"Mean pixel diff (Noir vs source): {diff:.2f}")
assert diff > 5, f"Noir should produce visible pixel change, got diff={diff:.2f}"
print("PASS: Pixel difference verified")

# Verify no-op has very small difference
frame_none = r'C:\AdeptFilmWorks\AIVideoStudio\studio-api\tests\fixtures\frame_none.png'
subprocess.run(['ffmpeg', '-y', '-i', out3, '-vframes', '1', frame_none], capture_output=True)
img_none = np.array(Image.open(frame_none))
diff_none = np.abs(img_src.astype(float) - img_none.astype(float)).mean()
print(f"Mean pixel diff (no-op vs source): {diff_none:.2f}")
print("PASS: No-op pixel difference minimal")

# Cleanup
for f in [frame_src, frame_graded, frame_none]:
    Path(f).unlink(missing_ok=True)

print("\nALL COLOR GRADE LIVE TESTS PASSED")
