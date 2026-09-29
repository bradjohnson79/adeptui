import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  LIBRARY_IMAGE_VISUAL_NOTICE_OCCUPIED,
  buildImageVisualClip,
  planLibraryImageClick,
  planLibraryImageDrop,
  visualTrackOccupied,
} from './libraryImageToVisual';

const asset = { id: 'img-1', tag: 'korri_front', filename: 'korri.png', kind: 'image' };

describe('visualTrackOccupied', () => {
  it('empty when no video_clips and no playable visual', () => {
    expect(visualTrackOccupied({ videoClips: [], playableTakes: [] })).toBe(false);
  });
  it('occupied when video_clips length > 0', () => {
    expect(visualTrackOccupied({ videoClips: [{ id: 'v1', start: 0, length: 5 }], playableTakes: [] })).toBe(true);
  });
  it('occupied when any playable visual exists', () => {
    expect(visualTrackOccupied({ videoClips: [], playableTakes: [{ id: 'bbclip_1', start: 0, length: 5 }] })).toBe(true);
  });
});

describe('planLibraryImageClick', () => {
  it('marks win even on empty Visual (Hop 6 Image-Frame)', () => {
    expect(planLibraryImageClick({ marksOk: true, videoClips: [], playableTakes: [], durationSec: 8, asset }).action).toBe(
      'place-marks',
    );
  });
  it('empty Visual + timeline click -> full-span image clip', () => {
    const plan = planLibraryImageClick({
      marksOk: false,
      videoClips: [],
      playableTakes: [],
      durationSec: 8,
      asset,
      clipId: 'imgclip_testempty',
    });
    expect(plan.action).toBe('add-full-span');
    if (plan.action !== 'add-full-span') return;
    expect(plan.clip.start).toBe(0);
    expect(plan.clip.length).toBe(8);
    expect(plan.clip.asset_id).toBe('img-1');
    expect(plan.clip.media_type).toBe('image');
    expect(plan.clip.mediaType).toBe('image');
    expect(plan.clip.id.startsWith('imgclip_')).toBe(true);
    expect(plan.clip.metadata.role).toBe('image_frame');
  });
  it('non-empty Visual + timeline click -> occupied-safe (no auto-add)', () => {
    const plan = planLibraryImageClick({
      marksOk: false,
      videoClips: [{ id: 'v1', start: 0, length: 5 }],
      playableTakes: [],
      durationSec: 8,
      asset,
    });
    expect(plan).toEqual({ action: 'occupied-safe', notice: LIBRARY_IMAGE_VISUAL_NOTICE_OCCUPIED });
  });
  it('playable visual without video_clips refuses click auto-add', () => {
    const plan = planLibraryImageClick({
      marksOk: false,
      videoClips: [],
      playableTakes: [{ id: 'bbclip_x', start: 0, length: 5 }],
      durationSec: 8,
      asset,
    });
    expect(plan.action).toBe('occupied-safe');
  });
});

describe('planLibraryImageDrop', () => {
  it('marks win on drop (Image-Frame place path)', () => {
    expect(
      planLibraryImageDrop({
        marksOk: true,
        videoClips: [{ id: 'imgclip_p1', start: 2, length: 3 }],
        durationSec: 10,
        dropTime: 4,
        asset,
      }).action,
    ).toBe('place-marks');
  });
  it('empty video_clips -> full-span even if caller would treat playable as occupied', () => {
    const plan = planLibraryImageDrop({
      marksOk: false,
      videoClips: [],
      durationSec: 6,
      dropTime: 1.5,
      asset,
      clipId: 'imgclip_dropempty',
    });
    expect(plan.action).toBe('add-full-span');
    if (plan.action !== 'add-full-span') return;
    expect(plan.clip.start).toBe(0);
    expect(plan.clip.length).toBe(6);
  });
  it('occupied Visual appends at drop time without replacing A|imgclip_|B', () => {
    const existing = [
      { id: 'orig-a', start: 0, length: 2 },
      { id: 'imgclip_p1', start: 2, length: 3 },
      { id: 'rtb_1', start: 5, length: 5 },
    ];
    const plan = planLibraryImageDrop({
      marksOk: false,
      videoClips: existing,
      durationSec: 12,
      dropTime: 10,
      asset,
      clipId: 'imgclip_dropappend',
    });
    expect(plan.action).toBe('add-at-time');
    if (plan.action !== 'add-at-time') return;
    expect(plan.clip.start).toBe(10);
    expect(plan.clip.length).toBe(2);
    expect(plan.clip.id).toBe('imgclip_dropappend');
  });
  it('drop onto occupied span appends after last clip', () => {
    const plan = planLibraryImageDrop({
      marksOk: false,
      videoClips: [{ id: 'v1', start: 0, length: 5 }],
      durationSec: 10,
      dropTime: 1,
      asset,
      clipId: 'imgclip_after',
    });
    expect(plan.action).toBe('add-at-time');
    if (plan.action !== 'add-at-time') return;
    expect(plan.clip.start).toBe(5);
    expect(plan.clip.length).toBe(2);
  });
});

describe('buildImageVisualClip shape', () => {
  it('matches Image-Frame / TimelineClip still contract', () => {
    const clip = buildImageVisualClip({ asset, start: 0, length: 5, id: 'imgclip_shape' });
    expect(clip).toMatchObject({
      id: 'imgclip_shape',
      start: 0,
      length: 5,
      asset_id: 'img-1',
      trim_start: 0,
      mediaType: 'image',
      media_type: 'image',
      metadata: { role: 'image_frame', referenceImageAssetId: 'img-1' },
    });
  });
});

describe('wiring source scan', () => {
  it('TimelineEditorShell click uses planner and keeps Hop 6 placeVisualImageRange first', () => {
    const src = readFileSync(new URL('./TimelineEditorShell.tsx', import.meta.url), 'utf8');
    const imageStart = src.indexOf('if (asset.kind === "image")');
    expect(imageStart).toBeGreaterThan(0);
    const imageBlock = src.slice(imageStart, imageStart + 4000);
    expect(imageBlock.indexOf('placeVisualImageRange')).toBeGreaterThan(0);
    expect(imageBlock.indexOf('placeVisualImageRange')).toBeLessThan(imageBlock.indexOf('planLibraryImageClick'));
    expect(imageBlock).toContain('occupied-safe');
    expect(imageBlock).toContain('add-full-span');
    expect(imageBlock).toContain('mutateTimeline');
  });
  it('DirectorTracks Visual drop places via planner', () => {
    const tracks = readFileSync(new URL('../DirectorTracks.tsx', import.meta.url), 'utf8');
    expect(tracks).toContain('planLibraryImageDrop');
    expect(tracks).toContain('data-testid="timeline-visual-drop"');
    expect(tracks).toContain('addImageFromLibrary(assetId, dropTime)');
    expect(tracks).toContain('placeVisualImageRange');
  });
});
