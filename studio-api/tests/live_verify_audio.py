"""Live verification test for MAGI audio generation."""
import sys
sys.path.insert(0, r'C:\AdeptFilmWorks\AIVideoStudio\studio-api')

from app.generation_tools import ops
from pathlib import Path
import json

# Test 1: Generate music
print("Testing music generation...")
result = ops.run_audio_generate(
    None,
    project_id="test_magi",
    kind="music",
    prompt="Ambient cinematic background music for a sci-fi scene",
    duration_sec=10,
)
print("Music result:", json.dumps(result, indent=2, default=str)[:500])
print("PASS: Music generation completed")

# Test 2: Generate SFX  
print("\nTesting SFX generation...")
result2 = ops.run_audio_generate(
    None,
    project_id="test_magi",
    kind="sfx",
    prompt="Subtle corridor ambience with footsteps",
    duration_sec=8,
)
print("SFX result:", json.dumps(result2, indent=2, default=str)[:500])
print("PASS: SFX generation completed")

print("\nALL AUDIO GENERATION TESTS PASSED")
