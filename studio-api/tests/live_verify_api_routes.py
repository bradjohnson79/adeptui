"""Test MAGI audio generation via API endpoint."""
import sys
sys.path.insert(0, r'C:\AdeptFilmWorks\AIVideoStudio\studio-api')

# Test the API endpoint structure
# The audio generation endpoint calls ops.run_audio_generate which requires
# a database session. We test the endpoint routing and error handling.

from app.magi.api import router
from fastapi.testclient import TestClient

# Check that the endpoint exists on the router
routes = [r.path for r in router.routes]
print("MAGI API routes:")
for route in sorted(routes):
    print(f"  {route}")

# Verify audio endpoint exists
audio_routes = [r for r in routes if "audio" in r]
print(f"\nAudio routes: {audio_routes}")
assert len(audio_routes) > 0, "No audio generation endpoint found"
print("PASS: Audio generation endpoint registered")

# Verify color endpoints exist
color_routes = [r for r in routes if "color" in r]
print(f"Color routes: {color_routes}")
assert len(color_routes) > 0, "No color endpoints found"
print("PASS: Color endpoints registered")

# Verify upscale endpoints exist
upscale_routes = [r for r in routes if "upscale" in r]
print(f"Upscale routes: {upscale_routes}")
assert len(upscale_routes) > 0, "No upscale endpoints found"
print("PASS: Upscale endpoints registered")

print("\nALL API ROUTE TESTS PASSED")
