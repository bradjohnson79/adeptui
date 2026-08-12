"""Frozen creator-facing preset catalogs + DSP mapping tables."""

from __future__ import annotations

from typing import Any

SPACE_PRESETS: dict[str, dict[str, Any]] = {
    "dry_booth": {"label": "Dry Recording Booth", "reverb_ms": 40, "wet": 0.02, "tail_ms": 20},
    "small_room": {"label": "Small Room", "reverb_ms": 180, "wet": 0.12, "tail_ms": 120},
    "bedroom": {"label": "Bedroom", "reverb_ms": 220, "wet": 0.14, "tail_ms": 160},
    "office": {"label": "Office", "reverb_ms": 260, "wet": 0.16, "tail_ms": 180},
    "living_room": {"label": "Living Room", "reverb_ms": 320, "wet": 0.18, "tail_ms": 220},
    "classroom": {"label": "Classroom", "reverb_ms": 420, "wet": 0.22, "tail_ms": 280},
    "large_hall": {"label": "Large Hall", "reverb_ms": 900, "wet": 0.35, "tail_ms": 700},
    "warehouse": {"label": "Warehouse", "reverb_ms": 1100, "wet": 0.38, "tail_ms": 850},
    "cathedral": {"label": "Cathedral", "reverb_ms": 1800, "wet": 0.48, "tail_ms": 1400},
    "cavern": {"label": "Cavern", "reverb_ms": 1600, "wet": 0.45, "tail_ms": 1200},
    "tunnel": {"label": "Tunnel", "reverb_ms": 700, "wet": 0.32, "tail_ms": 500},
    "stadium": {"label": "Stadium", "reverb_ms": 2000, "wet": 0.42, "tail_ms": 1600},
    "outdoor_open": {"label": "Outdoor Open Space", "reverb_ms": 80, "wet": 0.04, "tail_ms": 40},
    "forest": {"label": "Forest", "reverb_ms": 250, "wet": 0.1, "tail_ms": 180},
    "street": {"label": "Street", "reverb_ms": 150, "wet": 0.08, "tail_ms": 100},
    "spaceship_corridor": {"label": "Spaceship Corridor", "reverb_ms": 500, "wet": 0.28, "tail_ms": 360},
    "custom": {"label": "Custom", "reverb_ms": 300, "wet": 0.18, "tail_ms": 220},
}

DISTANCE_PRESETS: dict[str, dict[str, Any]] = {
    "extreme_close": {"label": "Extreme Close", "gain_db": 2.0, "hf_cut_hz": 16000, "latency_ms": 0},
    "close_up": {"label": "Close-Up", "gain_db": 1.0, "hf_cut_hz": 14000, "latency_ms": 0},
    "medium_close_up": {"label": "Medium Close-Up", "gain_db": 0.0, "hf_cut_hz": 12000, "latency_ms": 2},
    "medium": {"label": "Medium", "gain_db": -1.5, "hf_cut_hz": 10000, "latency_ms": 4},
    "long_shot": {"label": "Long Shot", "gain_db": -4.0, "hf_cut_hz": 7500, "latency_ms": 8},
    "very_distant": {"label": "Very Distant", "gain_db": -8.0, "hf_cut_hz": 5000, "latency_ms": 14},
    "offscreen_nearby": {"label": "Off-Screen Nearby", "gain_db": -2.0, "hf_cut_hz": 9000, "latency_ms": 5},
    "offscreen_distant": {"label": "Off-Screen Distant", "gain_db": -6.0, "hf_cut_hz": 6000, "latency_ms": 12},
    "custom": {"label": "Custom", "gain_db": -1.0, "hf_cut_hz": 11000, "latency_ms": 3},
}

DIRECTION_PRESETS: dict[str, dict[str, Any]] = {
    "center": {"label": "Center", "pan": 0.0},
    "slightly_left": {"label": "Slightly Left", "pan": -0.25},
    "left": {"label": "Left", "pan": -0.55},
    "far_left": {"label": "Far Left", "pan": -0.9},
    "slightly_right": {"label": "Slightly Right", "pan": 0.25},
    "right": {"label": "Right", "pan": 0.55},
    "far_right": {"label": "Far Right", "pan": 0.9},
    "behind": {"label": "Behind Listener", "pan": 0.0, "rear_bias": 0.7},
    "above": {"label": "Above", "pan": 0.0, "brightness": 1.1},
    "below": {"label": "Below", "pan": 0.0, "brightness": 0.85},
    "moving": {"label": "Moving", "pan": 0.15, "moving": True},
    "custom": {"label": "Custom", "pan": 0.0},
}

TONE_PRESETS: dict[str, dict[str, Any]] = {
    "natural": {"label": "Natural", "low_shelf_db": 0.0, "high_shelf_db": 0.0},
    "warm": {"label": "Warm", "low_shelf_db": 2.0, "high_shelf_db": -1.0},
    "bright": {"label": "Bright", "low_shelf_db": -0.5, "high_shelf_db": 2.5},
    "dark": {"label": "Dark", "low_shelf_db": 1.5, "high_shelf_db": -3.0},
    "high_tone": {"label": "High Tone", "low_shelf_db": -1.5, "high_shelf_db": 2.0},
    "low_tone": {"label": "Low Tone", "low_shelf_db": 2.5, "high_shelf_db": -1.5},
    "soft": {"label": "Soft", "low_shelf_db": 0.5, "high_shelf_db": -2.0},
    "full": {"label": "Full", "low_shelf_db": 1.5, "high_shelf_db": 0.5},
    "thin": {"label": "Thin", "low_shelf_db": -2.5, "high_shelf_db": 1.0},
    "muffled": {"label": "Muffled", "low_shelf_db": 1.0, "high_shelf_db": -5.0, "lp_hz": 3500},
    "distant": {"label": "Distant", "low_shelf_db": -0.5, "high_shelf_db": -2.5, "lp_hz": 7000},
    "intimate": {"label": "Intimate", "low_shelf_db": 1.0, "high_shelf_db": 1.0},
    "custom": {"label": "Custom", "low_shelf_db": 0.0, "high_shelf_db": 0.0},
}

DEVICE_PRESETS: dict[str, dict[str, Any]] = {
    "direct": {"label": "Direct Voice", "band_low_hz": 40, "band_high_hz": 16000, "drive": 0.0, "latency_ms": 0},
    "telephone": {"label": "Telephone", "band_low_hz": 300, "band_high_hz": 3400, "drive": 0.15, "latency_ms": 8},
    "mobile_phone": {"label": "Mobile Phone", "band_low_hz": 250, "band_high_hz": 4500, "drive": 0.12, "latency_ms": 6},
    "television": {"label": "Television", "band_low_hz": 120, "band_high_hz": 8000, "drive": 0.08, "latency_ms": 4},
    "radio": {"label": "Radio", "band_low_hz": 200, "band_high_hz": 5000, "drive": 0.18, "latency_ms": 7},
    "intercom": {"label": "Intercom", "band_low_hz": 400, "band_high_hz": 3800, "drive": 0.22, "latency_ms": 10},
    "pa": {"label": "Public Address System", "band_low_hz": 180, "band_high_hz": 6000, "drive": 0.25, "latency_ms": 12},
    "stadium_pa": {"label": "Stadium PA", "band_low_hz": 160, "band_high_hz": 5500, "drive": 0.3, "latency_ms": 18},
    "podcast_mic": {"label": "Podcast Microphone", "band_low_hz": 60, "band_high_hz": 14000, "drive": 0.05, "latency_ms": 1},
    "studio_broadcast": {"label": "Studio Broadcast", "band_low_hz": 50, "band_high_hz": 15000, "drive": 0.04, "latency_ms": 1},
    "security_speaker": {"label": "Security Speaker", "band_low_hz": 450, "band_high_hz": 3200, "drive": 0.28, "latency_ms": 9},
    "helmet_comms": {"label": "Helmet Communications", "band_low_hz": 350, "band_high_hz": 4000, "drive": 0.2, "latency_ms": 11},
    "spaceship_comms": {"label": "Spaceship Communications", "band_low_hz": 320, "band_high_hz": 4200, "drive": 0.24, "latency_ms": 12},
    "walkie_talkie": {"label": "Walkie-Talkie", "band_low_hz": 400, "band_high_hz": 3000, "drive": 0.32, "latency_ms": 10},
    "damaged_transmission": {"label": "Damaged Transmission", "band_low_hz": 500, "band_high_hz": 2800, "drive": 0.4, "latency_ms": 16},
    "custom": {"label": "Custom", "band_low_hz": 100, "band_high_hz": 10000, "drive": 0.1, "latency_ms": 5},
}

WALLA_PRESETS: dict[str, dict[str, Any]] = {
    "none": {"label": "None", "level": 0.0},
    "light_room": {"label": "Light Room Walla", "level": 0.08},
    "busy_room": {"label": "Busy Room Walla", "level": 0.16},
    "restaurant": {"label": "Restaurant Crowd", "level": 0.18},
    "office": {"label": "Office Activity", "level": 0.12},
    "street": {"label": "Street Crowd", "level": 0.2},
    "stadium": {"label": "Stadium Crowd", "level": 0.28},
    "audience_murmur": {"label": "Audience Murmur", "level": 0.1},
    "audience_reaction": {"label": "Audience Reaction", "level": 0.22},
    "distant_conversation": {"label": "Distant Conversation", "level": 0.09},
    "party": {"label": "Party Background", "level": 0.24},
    "command_center": {"label": "Command Center", "level": 0.11},
    "custom": {"label": "Custom", "level": 0.12},
}

WALLA_LEVEL_SCALE = {"subtle": 0.6, "moderate": 1.0, "present": 1.4}
