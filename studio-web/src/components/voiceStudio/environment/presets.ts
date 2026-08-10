/** Creator-facing Voice Environment presets (M5.2 frozen catalogs). */

export type PresetOption = {
  id: string;
  label: string;
  description: string;
};

export const SPACE_PRESETS: readonly PresetOption[] = [
  { id: "dry_booth", label: "Dry Recording Booth", description: "Tight, controlled acoustics with almost no room sound." },
  { id: "small_room", label: "Small Room", description: "Close reflections and a compact, intimate acoustic presence." },
  { id: "bedroom", label: "Bedroom", description: "Soft furnishings and gentle close reflections." },
  { id: "office", label: "Office", description: "Modest room tone with light hard-surface reflections." },
  { id: "living_room", label: "Living Room", description: "Comfortable domestic space with mild bounce." },
  { id: "classroom", label: "Classroom", description: "Harder surfaces and a bit more room contribution." },
  { id: "large_hall", label: "Large Hall", description: "Longer reflections and a spacious presence." },
  { id: "warehouse", label: "Warehouse", description: "Industrial volume with delayed reflections." },
  { id: "cathedral", label: "Cathedral", description: "Grand, lingering reverberation." },
  { id: "cavern", label: "Cavern", description: "Deep, dark natural echoes." },
  { id: "tunnel", label: "Tunnel", description: "Focused reflections that stretch along a corridor." },
  { id: "stadium", label: "Stadium", description: "Huge open volume with distant bounce." },
  { id: "outdoor_open", label: "Outdoor Open Space", description: "Open air with little enclosed reflection." },
  { id: "forest", label: "Forest", description: "Soft outdoor scatter and natural hush." },
  { id: "street", label: "Street", description: "Open urban air with light environmental bounce." },
  { id: "spaceship_corridor", label: "Spaceship Corridor", description: "Metallic corridor with reflective brightness." },
  { id: "custom", label: "Custom", description: "Describe the acoustic environment yourself." },
] as const;

export const DISTANCE_PRESETS: readonly PresetOption[] = [
  { id: "extreme_close", label: "Extreme Close", description: "Very intimate proximity with strong presence." },
  { id: "close_up", label: "Close-Up", description: "Near the listener with clear detail." },
  { id: "medium_close_up", label: "Medium Close-Up", description: "Conversational distance for dialogue." },
  { id: "medium", label: "Medium", description: "Natural scene distance with balanced room." },
  { id: "long_shot", label: "Long Shot", description: "Farther away with more space contribution." },
  { id: "very_distant", label: "Very Distant", description: "Far placement with softer highs and quieter level." },
  { id: "offscreen_nearby", label: "Off-Screen Nearby", description: "Just out of frame but still close." },
  { id: "offscreen_distant", label: "Off-Screen Distant", description: "Heard from farther off-screen." },
  { id: "custom", label: "Custom", description: "Describe how far away the speaker should feel." },
] as const;

export const DIRECTION_PRESETS: readonly PresetOption[] = [
  { id: "center", label: "Center", description: "Directly in front of the listener." },
  { id: "slightly_left", label: "Slightly Left", description: "A gentle left-side placement." },
  { id: "left", label: "Left", description: "Clearly from the left." },
  { id: "far_left", label: "Far Left", description: "Strong left-edge placement." },
  { id: "slightly_right", label: "Slightly Right", description: "A gentle right-side placement." },
  { id: "right", label: "Right", description: "Clearly from the right." },
  { id: "far_right", label: "Far Right", description: "Strong right-edge placement." },
  { id: "behind", label: "Behind Listener", description: "Coming from behind." },
  { id: "above", label: "Above", description: "Heard from above." },
  { id: "below", label: "Below", description: "Heard from below." },
  { id: "moving", label: "Moving", description: "A shifting source across the scene." },
  { id: "custom", label: "Custom", description: "Describe where the voice should come from." },
] as const;

export const TONE_PRESETS: readonly PresetOption[] = [
  { id: "natural", label: "Natural", description: "Scene presentation stays close to the approved voice." },
  { id: "warm", label: "Warm", description: "Slightly softer, warmer scene presentation." },
  { id: "bright", label: "Bright", description: "A bit more sparkle in the scene presentation." },
  { id: "dark", label: "Dark", description: "Darker, heavier presentation in the scene." },
  { id: "high_tone", label: "High Tone", description: "Lifts the scene presentation upward." },
  { id: "low_tone", label: "Low Tone", description: "Settles the scene presentation lower." },
  { id: "soft", label: "Soft", description: "Gentle, rounded presentation." },
  { id: "full", label: "Full", description: "Richer body in the scene mix." },
  { id: "thin", label: "Thin", description: "Leaner scene presentation." },
  { id: "muffled", label: "Muffled", description: "Softened detail, as if partly covered." },
  { id: "distant", label: "Distant", description: "Airier, farther tonal presentation." },
  { id: "intimate", label: "Intimate", description: "Close, personal tonal presentation." },
  { id: "custom", label: "Custom", description: "Describe the tonal treatment for the scene." },
] as const;

export const DEVICE_PRESETS: readonly PresetOption[] = [
  { id: "direct", label: "Direct Voice", description: "Heard naturally in the space, not through a device." },
  { id: "telephone", label: "Telephone", description: "Classic phone coloration and narrowed band." },
  { id: "mobile_phone", label: "Mobile Phone", description: "Modern handset transmission character." },
  { id: "television", label: "Television", description: "Screen-speaker presentation." },
  { id: "radio", label: "Radio", description: "Broadcast radio coloration." },
  { id: "intercom", label: "Intercom", description: "Narrow transmitted voice with light speaker coloration and subtle mechanical ambience." },
  { id: "pa", label: "Public Address System", description: "Public address projection and speaker grit." },
  { id: "stadium_pa", label: "Stadium PA", description: "Large-venue announcement character." },
  { id: "podcast_mic", label: "Podcast Microphone", description: "Close podcast mic presence." },
  { id: "studio_broadcast", label: "Studio Broadcast", description: "Polished broadcast-booth delivery path." },
  { id: "security_speaker", label: "Security Speaker", description: "Small security speaker grit." },
  { id: "helmet_comms", label: "Helmet Communications", description: "Enclosed helmet radio presence." },
  { id: "spaceship_comms", label: "Spaceship Communications", description: "Shipboard comms coloration." },
  { id: "walkie_talkie", label: "Walkie-Talkie", description: "Push-to-talk radio character." },
  { id: "damaged_transmission", label: "Damaged Transmission", description: "Broken or degraded transmission." },
  { id: "custom", label: "Custom", description: "Describe the device or transmission." },
] as const;

export const WALLA_PRESETS: readonly PresetOption[] = [
  { id: "none", label: "None", description: "No background vocal atmosphere." },
  { id: "light_room", label: "Light Room Walla", description: "Soft presence of people nearby." },
  { id: "busy_room", label: "Busy Room Walla", description: "Active room conversation texture." },
  { id: "restaurant", label: "Restaurant Crowd", description: "Dining-room crowd murmur." },
  { id: "office", label: "Office Activity", description: "Workplace chatter and movement." },
  { id: "street", label: "Street Crowd", description: "Outdoor crowd atmosphere." },
  { id: "stadium", label: "Stadium Crowd", description: "Large audience presence." },
  { id: "audience_murmur", label: "Audience Murmur", description: "Quiet audience undercurrent." },
  { id: "audience_reaction", label: "Audience Reaction", description: "Reactive crowd responses." },
  { id: "distant_conversation", label: "Distant Conversation", description: "Far-off talking." },
  { id: "party", label: "Party Background", description: "Social party walla." },
  { id: "command_center", label: "Command Center", description: "Ops-room activity and muted voices." },
  { id: "custom", label: "Custom", description: "Describe the background voices and activity." },
] as const;
