"""The closed tool registry: the single place a definition is bound to a handler.

Binding lives in one table with one entry per declared tool. There is no dynamic lookup, no
name-to-import resolution, and no way to register a tool at runtime — if a tool isn't in
`_READ_HANDLERS` or `_MUTATION_HANDLERS` below, it cannot execute, and the module refuses to
import if a declared tool has no binding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from ..errors import TOOL_KIND_MISMATCH, TOOL_NOT_FOUND, TOOL_SCHEMA_VERSION_MISMATCH, CoDirectorError
from .definitions import (
    TOOL_DEFINITIONS,
    ToolContext,
    ToolDefinition,
    ToolPreview,
)
from .aliases import resolve_tool_id
from .handlers import (
    audio_studio_tools,
    avatar_m412,
    bible_domain,
    bible_read,
    character_creator,
    character_identity,
    continuity_w5,
    director_timeline_tools,
    environment_reference_sheet,
    scene_references_w6p,
    generation_tools,
    image_pipeline_tools,
    library,
    media_execution,
    magi,
    minimax_h3_tools,
    multi_shot_tools,
    posecraft,
    project,
    project_context,
    project_decisions,
    system_status,
    prompt_intelligence,
    scenes,
    setup_guided,
    storyboard,
    spatial_m411,
    system,
    timeline_references,
    vision,
    voice_environment,
    voice_m410,
    voice_performance,
    scriptwriter_tools,
    docker_runtime_tools,
    wave3_reads,
    wave4_plans,
    script_timing,
    storyboard_timing,
    pillar_comparison,
    production,
)

ReadHandler = Callable[[ToolContext, dict[str, Any]], Awaitable[dict[str, Any]]]
PreviewFn = Callable[[ToolContext, dict[str, Any]], ToolPreview]
ApplyFn = Callable[[ToolContext, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class MutationHandler:
    preview: PreviewFn
    apply: ApplyFn


_READ_HANDLERS: dict[str, ReadHandler] = {
    "get_project_profile": project.get_project_profile,
    "get_project_status": project.get_project_status,
    "project.production_snapshot": production.read_production_snapshot,
    "production.memory": production.read_production_memory,
    "production.resolve_reference": production.resolve_production_reference,
    "candidate.list": production.list_candidates,
    "candidate.resolve": production.resolve_candidate,
    "list_scenes": scenes.list_scenes,
    "get_scene": scenes.get_scene,
    "get_active_scene": scenes.get_active_scene,
    "get_current_bible_version": bible_read.get_current_bible_version,
    "get_bible_entity": bible_read.get_bible_entity,
    "list_bible_entities": bible_read.list_bible_entities,
    "get_relevant_bible_context": bible_read.get_relevant_bible_context,
    "get_production_bible_summary": bible_domain.get_production_bible_summary,
    "get_scene_bible_context": bible_domain.get_scene_bible_context,
    "get_character_bible_context": bible_domain.get_character_bible_context,
    "get_location_bible_context": bible_domain.get_location_bible_context,
    "list_canon_records": bible_domain.list_canon_records,
    "list_continuity_warnings": bible_domain.list_continuity_warnings,
    "get_generation_reference_package": bible_domain.get_generation_reference_package,
    "get_provider_health": system.get_provider_health,
    "get_selected_model": system.get_selected_model,
    "get_comfyui_health": system.get_comfyui_health,
    "get_source_manager_status": system.get_source_manager_status,
    "get_reference_capabilities": system.get_reference_capabilities,
    "get_engine_capabilities": system.get_engine_capabilities,
    "get_cloud_render_status": system.get_cloud_render_status,
    "hosted_providers.recommend": system.recommend_hosted_provider,
    "vision_validation_status": vision.vision_validation_status,
    "vision_validation_report": vision.vision_validation_report,
    "get_timeline_image": timeline_references.get_timeline_image,
    "list_timeline_images": timeline_references.list_timeline_images,
    "get_reference_set": timeline_references.get_reference_set,
    "list_reference_bindings": timeline_references.list_reference_bindings,
    "build_generation_reference_package": timeline_references.build_generation_reference_package,
    "suggest_reference_bindings": timeline_references.suggest_reference_bindings,
    "get_library_folder_map": library.get_library_folder_map,
    "get_library_context_summary": library.get_library_context_summary,
    "resolve_library_location": library.resolve_library_location_tool,
    "search_library_assets": library.search_library_assets_tool,
    "plan_library_storage": library.plan_library_storage,
    "link_bible_entity_folder": library.link_bible_entity_folder_tool,
    "get_generation_tools_catalog": generation_tools.get_generation_tools_catalog,
    "list_character_profiles": character_identity.list_character_profiles,
    "inspect_character_profile": character_identity.inspect_character_profile,
    "inspect_character_coverage": character_identity.inspect_character_coverage,
    "inspect_character_voice": character_identity.inspect_character_voice,
    "character_creator.get_motion_profile": character_creator.get_motion_profile,
    "character_creator.get_performance_bible": character_creator.get_performance_bible,
    "character_creator.get_relationship_graph": character_creator.get_relationship_graph,
    "character_creator.get_prompt_package": character_creator.get_prompt_package,
    "character_creator.get_visual_sheet_status": character_creator.get_visual_sheet_status,
    "character_creator.get_voice_status": character_creator.get_voice_status,
    "character_creator.get_voice_profile": character_creator.get_voice_profile,
    "character_creator.get_voice_candidates": character_creator.get_voice_candidates,
    "character_creator.compare_voice_candidates": character_creator.compare_voice_candidates,
    "character_creator.get_pronunciation_profile": character_creator.get_pronunciation_profile,
    "character_creator.get_reaction_coverage": character_creator.get_reaction_coverage,
    "character_creator.open_voice_creator": character_creator.open_voice_creator,
    "voice.inspect_studio": voice_environment.inspect_studio,
    "voice.inspect_character": voice_environment.inspect_character,
    "voice.inspect_identity": voice_environment.inspect_identity,
    "voice.inspect_performance": voice_environment.inspect_performance,
    "voice.inspect_dialogue": voice_environment.inspect_dialogue,
    "voice.inspect_takes": voice_environment.inspect_takes,
    "voice_performance.get_status": voice_performance.get_status,
    "voice_performance.get_character_readiness": voice_performance.get_character_readiness,
    "voice_performance.parse_markup": voice_performance.parse_markup,
    "voice_performance.preview_plan": voice_performance.preview_plan,
    "voice_performance.validate_plan": voice_performance.validate_plan,
    "voice_performance.get_provider_translation": voice_performance.get_provider_translation,
    "voice_performance.get_pronunciation_issues": voice_performance.get_pronunciation_issues,
    "voice_performance.get_reaction_coverage": voice_performance.get_reaction_coverage,
    "voice_performance.open_workspace": voice_performance.open_workspace,
    "workspace.open_scriptwriter": scriptwriter_tools.open_scriptwriter,
    "voice.performance_context": voice_m410.performance_context,
    "voice.analyze_dialogue": voice_m410.analyze_dialogue,
    "voice.create_performance_plan": voice_m410.create_performance_plan,
    "voice.create_scene_performance_plan": voice_m410.create_scene_performance_plan,
    "voice.suggest_take_variations": voice_m410.suggest_take_variations,
    "voice.compare_takes": voice_m410.compare_takes,
    "voice.adjust_performance": voice_m410.adjust_performance,
    "voice.prepare_timeline_dialogue": voice_m410.prepare_timeline_dialogue,
    "voice.prepare_lipsync": voice_m410.prepare_lipsync,
    "voice_environment.inspect_scene": voice_environment.inspect_scene,
    "voice_environment.inspect_location": voice_environment.inspect_location,
    "voice_environment.inspect_spatial_map": voice_environment.inspect_spatial_map,
    "voice_environment.inspect_performance": voice_environment.inspect_environment_performance,
    "voice_environment.inspect_profile": voice_environment.inspect_profile,
    "voice_environment.list_profiles": voice_environment.list_profiles,
    "voice_environment.list_renders": voice_environment.list_renders,
    "voice_environment.inspect_runtime": voice_environment.inspect_runtime,
    "voice_environment.inspect_timeline_link": voice_environment.inspect_timeline_link,
    "voice_environment.inspect_lipsync_link": voice_environment.inspect_lipsync_link,
    "voice_environment.preview_plan": voice_environment.preview_plan,
    "avatar.inspect": avatar_m412.inspect,
    "avatar.get_provider_status": avatar_m412.get_provider_status,
    "avatar.get_script_context": avatar_m412.get_script_context,
    "avatar.get_voice_context": avatar_m412.get_voice_context,
    "avatar.get_job": avatar_m412.get_job,
    "avatar.get_section": avatar_m412.get_section,
    "avatar.compare_sections": avatar_m412.compare_sections,
    "avatar.check_continuity": avatar_m412.check_continuity,
    "spatial.list_maps": spatial_m411.list_maps,
    "spatial.get_map": spatial_m411.get_map,
    "spatial.inspect_scene": spatial_m411.inspect_scene,
    "spatial.list_cameras": spatial_m411.list_cameras,
    "spatial.get_camera_view": spatial_m411.get_camera_view,
    "spatial.check_visibility": spatial_m411.check_visibility,
    "spatial.check_consistency": spatial_m411.check_consistency,
    "spatial.build_reference_bundle": spatial_m411.build_reference_bundle,
    "audio.status": audio_studio_tools.status,
    "audio.library": audio_studio_tools.library,
    "audio.scene_status": audio_studio_tools.scene_status,
    "audio.preview_music": audio_studio_tools.preview_music,
    "audio.preview_sfx": audio_studio_tools.preview_sfx,
    "audio.preview_ambience": audio_studio_tools.preview_ambience,
    "audio.compare_candidates": audio_studio_tools.compare_candidates,
    "audio.get_batch": audio_studio_tools.get_batch,
    "audio.open_studio": audio_studio_tools.open_studio,
    "character_creator.inspect_readiness": character_creator.inspect_readiness,
    "character_creator.build_reference_plan": character_creator.build_reference_plan,
    "character_creator.build_expression_plan": character_creator.build_expression_plan,
    "character_creator.build_pose_plan": character_creator.build_pose_plan,
    "character_creator.build_voice_plan": character_creator.build_voice_plan,
    "character_creator.build_wardrobe_plan": character_creator.build_wardrobe_plan,
    "character_creator.build_continuity_plan": character_creator.build_continuity_plan,
    "character_creator.audit_profile": character_creator.audit_profile,
    # Wave 3 gap tools + canonical aliases (same handlers as snake_case where noted)
    "project.get_summary": wave3_reads.project_get_summary,
    "project.list_blockers": wave3_reads.project_list_blockers,
    "script.list": wave3_reads.script_list,
    "script.get": wave3_reads.script_get,
    "script.search": wave3_reads.script_search,
    "script.inspect": scriptwriter_tools.script_inspect,
    "script.scene_context": scriptwriter_tools.script_scene_context,
    "script.character_context": scriptwriter_tools.script_character_context,
    "script.analyze_structure": scriptwriter_tools.script_analyze_structure,
    "script.analyze_scene": scriptwriter_tools.script_analyze_scene,
    "script.analyze_dialogue": scriptwriter_tools.script_analyze_dialogue,
    "script.analyze_continuity": scriptwriter_tools.script_analyze_continuity,
    "script.suggest_revision": scriptwriter_tools.script_suggest_revision,
    "script.generate_outline": scriptwriter_tools.script_generate_outline,
    "script.generate_beat_sheet": scriptwriter_tools.script_generate_beat_sheet,
    "runtime.list": docker_runtime_tools.runtime_list,
    "runtime.inspect": docker_runtime_tools.runtime_inspect,
    "runtime.test": docker_runtime_tools.runtime_test,
        "setup.search_components": setup_guided.search_components,
    "setup.inspect_component": setup_guided.inspect_component,
    "setup.compare_components": setup_guided.compare_components,
    "setup.inspect_hardware": setup_guided.inspect_hardware,
    "setup.inspect_dependencies": setup_guided.inspect_dependencies,
    "setup.inspect_license": setup_guided.inspect_license,
    "setup.inspect_source": setup_guided.inspect_source,
    "setup.build_install_plan": setup_guided.build_install_plan,
    "setup.get_install_status": setup_guided.get_install_status,
    "setup.diagnose_failure": setup_guided.diagnose_failure,
    "setup.list_repair_options": setup_guided.list_repair_options,
    "setup.list_recipes": setup_guided.list_recipes,
    "setup.inspect_recipe": setup_guided.inspect_recipe,
    "setup.get_certification": setup_guided.get_certification,
    "setup.check_updates": setup_guided.check_updates,
    "setup.get_monitor_status": setup_guided.get_monitor_status,
    "scene.search": wave3_reads.scene_search,
    "scene.list_characters": wave3_reads.scene_list_characters,
    "scene.list_assets": wave3_reads.scene_list_assets,
    "character.search": wave3_reads.character_search,
    "production_bible.search": wave3_reads.production_bible_search,
    "asset.get": wave3_reads.asset_get,
    "asset.list": wave3_reads.asset_list,
    "asset.search": wave3_reads.asset_list,
    "asset.list_by_character": wave3_reads.asset_list_by_character,
    "production_plan.list": wave4_plans.production_plan_list,
    "production_plan.get": wave4_plans.production_plan_get,
    "production_plan.get_version": wave4_plans.production_plan_get_version,
    "production_plan.list_versions": wave4_plans.production_plan_list_versions,
    "production_plan.list_events": wave4_plans.production_plan_list_events,
    "production_plan.validate": wave4_plans.production_plan_validate,
    "production_plan.get_readiness": wave4_plans.production_plan_get_readiness,
    "proposal.list": wave3_reads.proposal_list,
    "proposal.get": wave3_reads.proposal_get,
    "job.list": wave3_reads.job_list,
    "job.get": wave3_reads.job_get,
    "continuity.list_findings": wave3_reads.continuity_list_findings,
    "continuity.get_finding": wave3_reads.continuity_get_finding,
    "references.list": scene_references_w6p.list_references,
    "references.get": scene_references_w6p.get_reference,
    "references.get_inherited": scene_references_w6p.get_inherited,
    "references.get_readiness": scene_references_w6p.get_readiness,
    "references.preview_selection": scene_references_w6p.preview_selection,
    "references.preflight": scene_references_w6p.preflight,
        "continuity.search_identities": continuity_w5.search_identities,
    "continuity.get_identity": continuity_w5.get_identity,
    "continuity.get_identity_version": continuity_w5.get_identity_version,
    "continuity.list_variants": continuity_w5.list_variants,
    "continuity.get_reference_readiness": continuity_w5.get_reference_readiness,
    "continuity.preview_packet": continuity_w5.preview_packet,
    "continuity.preflight": continuity_w5.preflight,
    "continuity.get_evaluation": continuity_w5.get_evaluation,
    "continuity.list_issues": continuity_w5.list_issues,
        "timeline.get_workspace": director_timeline_tools.get_workspace,
    "timeline.get_playhead": director_timeline_tools.get_playhead,
    "timeline.get_settings": director_timeline_tools.get_settings,
    "timeline.get_guidance_priority": director_timeline_tools.get_guidance_priority,
    "timeline.inspect_batches": director_timeline_tools.inspect_batches,
    "timeline.preflight": director_timeline_tools.preflight,
    "timeline.explain_asset_reference_name": director_timeline_tools.explain_asset_reference_name,
    "timeline.focus_ui": director_timeline_tools.focus_ui,
    "timeline.inspect_layout": director_timeline_tools.inspect_layout,
    "timeline.inspect_lipsync": director_timeline_tools.inspect_lipsync,
    "timeline.validate_lipsync": director_timeline_tools.validate_lipsync,
    "workspace.get_active_context": wave3_reads.workspace_get_active_context,
    "system.list_capabilities": wave3_reads.system_list_capabilities,
    "scene.list": scenes.list_scenes,
    "scene.get": scenes.get_scene,
    "character.list": character_identity.list_character_profiles,
    "character.get": character_identity.inspect_character_profile,
    "production_bible.get_summary": bible_domain.get_production_bible_summary,
    "production_bible.list_entries": bible_read.list_bible_entities,
    "production_bible.get_entry": bible_read.get_bible_entity,
    "asset.list_by_scene": wave3_reads.scene_list_assets,
    "prompt.enhance": prompt_intelligence.prompt_enhance,
    "prompt.analyze": prompt_intelligence.prompt_analyze,
    "prompt.benchmark_plan": prompt_intelligence.prompt_benchmark_plan,
    "prompt.benchmark_status": prompt_intelligence.prompt_benchmark_status,
    "prompt.compare_results": prompt_intelligence.prompt_compare_results,
    "prompt.recommend_strategy": prompt_intelligence.prompt_recommend_strategy,
    "prompt.review_evidence": prompt_intelligence.prompt_review_evidence,
    "prompt.certification_status": prompt_intelligence.prompt_certification_status,
    "system.status_check": system_status.status_check,
    "system.status_summary": system_status.status_summary,
    "system.status_check_component": system_status.status_check_component,
    "system.status_list_blockers": system_status.status_list_blockers,
    "system.status_list_warnings": system_status.status_list_warnings,
    "system.status_recovery_options": system_status.status_recovery_options,
    "system.deep_diagnostic": system_status.deep_diagnostic,
    "image_pipeline.analyze_request": image_pipeline_tools.analyze_request,
    "image_pipeline.get_readiness": image_pipeline_tools.get_readiness,
    "image_pipeline.get_job": image_pipeline_tools.get_job,
    "image_pipeline.preview_posecraft": image_pipeline_tools.preview_posecraft,
    "multi_shot.list_plans": multi_shot_tools.list_plans,
    "multi_shot.get_plan": multi_shot_tools.get_plan,
    "multi_shot.ers_recommendation": multi_shot_tools.ers_recommendation,
    "ers.list_sheets": environment_reference_sheet.list_sheets,
    "ers.get_sheet": environment_reference_sheet.get_sheet,
    "minimax_h3.capability": minimax_h3_tools.capability,
    "minimax_h3.get_plan": minimax_h3_tools.get_plan_tool,
    "minimax_h3.preflight_status": minimax_h3_tools.preflight_status,
    "posecraft.get_status": posecraft.get_status,
    "posecraft.get_scene": posecraft.get_scene,
    "posecraft.export_reference": posecraft.export_reference,
    "posecraft.inspect_scene": posecraft.inspect_scene,
    "posecraft.list_scenes": posecraft.list_scenes,
    "magi.inspect_sequence": magi.inspect_sequence,
    "magi.inspect_clip": magi.inspect_clip,
    "magi.inspect_tracks": magi.inspect_tracks,
    "magi.inspect_selection": magi.inspect_selection,
    "magi.inspect_timeline_lineage": magi.inspect_timeline_lineage,
    "magi.readiness": magi.readiness,
    "project.read_context": project_context.read_project_context,
    "script.estimate_timing": script_timing.read_script_timing,
    "storyboard.estimate_runtime": storyboard_timing.read_storyboard_timing,
    "foundation.compare_pillars": pillar_comparison.read_pillar_comparison,
}

_MUTATION_HANDLERS: dict[str, MutationHandler] = {
    "create_draft_character_profile": MutationHandler(
        character_identity.preview_create_draft_character_profile,
        character_identity.apply_create_draft_character_profile,
    ),
    "character_creator.create_from_brief": MutationHandler(
        character_creator.preview_create_from_brief,
        character_creator.apply_create_from_brief,
    ),
    "character_creator.create_from_script": MutationHandler(
        character_creator.preview_create_from_script,
        character_creator.apply_create_from_script,
    ),
    "character_creator.propose_traits": MutationHandler(
        character_creator.preview_propose_traits,
        character_creator.apply_propose_traits,
    ),
    "character_creator.propose_relationships": MutationHandler(
        character_creator.preview_propose_relationships,
        character_creator.apply_propose_relationships,
    ),
    "character_creator.propose_visual_sheet": MutationHandler(
        character_creator.preview_propose_visual_sheet,
        character_creator.apply_propose_visual_sheet,
    ),
    "character_creator.advance_visual_sheet": MutationHandler(
        character_creator.preview_advance_visual_sheet,
        character_creator.apply_advance_visual_sheet,
    ),
    "character_creator.preview_voice_design": MutationHandler(
        character_creator.preview_voice_design,
        character_creator.apply_preview_voice_design,
    ),
    "character_creator.generate_voice_candidates": MutationHandler(
        character_creator.preview_generate_voice_candidates,
        character_creator.apply_generate_voice_candidates,
    ),
    "character_creator.refine_voice_candidate": MutationHandler(
        character_creator.preview_refine_voice_candidate,
        character_creator.apply_refine_voice_candidate,
    ),
    "character_creator.approve_voice_candidate": MutationHandler(
        character_creator.preview_approve_voice_candidate,
        character_creator.apply_approve_voice_candidate,
    ),
    "character_creator.validate_clone_source": MutationHandler(
        character_creator.preview_validate_clone_source,
        character_creator.apply_validate_clone_source,
    ),
    "character_creator.generate_voice_clone": MutationHandler(
        character_creator.preview_generate_voice_clone,
        character_creator.apply_generate_voice_clone,
    ),
    "character_creator.test_pronunciation": MutationHandler(
        character_creator.preview_test_pronunciation,
        character_creator.apply_test_pronunciation,
    ),
    "character_creator.generate_reactions": MutationHandler(
        character_creator.preview_generate_reactions,
        character_creator.apply_generate_reactions,
    ),
    "character_creator.submit_for_review": MutationHandler(
        character_creator.preview_submit_for_review,
        character_creator.apply_submit_for_review,
    ),
    "voice_performance.generate_segments": MutationHandler(
        voice_performance.preview_generate_segments,
        voice_performance.apply_generate_segments,
    ),
    "voice_performance.retry_segment": MutationHandler(
        voice_performance.preview_retry_segment,
        voice_performance.apply_retry_segment,
    ),
    "voice_performance.refine_segment": MutationHandler(
        voice_performance.preview_refine_segment,
        voice_performance.apply_refine_segment,
    ),
    "voice_performance.compare_takes": MutationHandler(
        voice_performance.preview_compare_takes,
        voice_performance.apply_compare_takes,
    ),
    "voice_performance.approve_take": MutationHandler(
        voice_performance.preview_approve_take,
        voice_performance.apply_approve_take,
    ),
    "voice_performance.assemble_dialogue": MutationHandler(
        voice_performance.preview_assemble_dialogue,
        voice_performance.apply_assemble_dialogue,
    ),
    "voice_performance.place_on_timeline": MutationHandler(
        voice_performance.preview_place_on_timeline,
        voice_performance.apply_place_on_timeline,
    ),
    "voice.apply_performance_plan": MutationHandler(
        voice_m410.preview_apply_performance_plan,
        voice_m410.apply_apply_performance_plan,
    ),
    "voice.select_character": MutationHandler(
        voice_environment.preview_select_character,
        voice_environment.apply_select_character,
    ),
    "voice.create_character_handoff": MutationHandler(
        voice_environment.preview_create_character_handoff,
        voice_environment.apply_create_character_handoff,
    ),
    "voice.create_identity_plan": MutationHandler(
        voice_environment.preview_create_identity_plan,
        voice_environment.apply_create_identity_plan,
    ),
    "voice_environment.create_profile": MutationHandler(
        voice_environment.preview_create_profile,
        voice_environment.apply_create_profile,
    ),
    "voice_environment.update_profile": MutationHandler(
        voice_environment.preview_update_profile,
        voice_environment.apply_update_profile,
    ),
    "voice_environment.apply_codirector_recommendation": MutationHandler(
        voice_environment.preview_apply_codirector_recommendation,
        voice_environment.apply_apply_codirector_recommendation,
    ),
    "voice_environment.create_preview": MutationHandler(
        voice_environment.preview_create_preview,
        voice_environment.apply_create_preview,
    ),
    "voice_environment.render": MutationHandler(
        voice_environment.preview_render,
        voice_environment.apply_render,
    ),
    "voice_environment.approve": MutationHandler(
        voice_environment.preview_approve,
        voice_environment.apply_approve,
    ),
    "voice_environment.create_alternate": MutationHandler(
        voice_environment.preview_create_alternate,
        voice_environment.apply_create_alternate,
    ),
    "voice_environment.apply_to_scene": MutationHandler(
        voice_environment.preview_apply_to_scene,
        voice_environment.apply_apply_to_scene,
    ),
    "voice_environment.prepare_timeline": MutationHandler(
        voice_environment.preview_prepare_timeline,
        voice_environment.apply_prepare_timeline,
    ),
    "voice_environment.prepare_lipsync": MutationHandler(
        voice_environment.preview_prepare_lipsync,
        voice_environment.apply_prepare_lipsync,
    ),
    "voice_environment.open_audio_studio": MutationHandler(
        voice_environment.preview_open_audio_studio,
        voice_environment.apply_open_audio_studio,
    ),
    "voice_environment.request_repair": MutationHandler(
        voice_environment.preview_request_repair,
        voice_environment.apply_request_repair,
    ),
    "voice.approve_take": MutationHandler(
        voice_m410.preview_approve_take,
        voice_m410.apply_approve_take,
    ),
    "voice.replace_timeline_dialogue": MutationHandler(
        voice_m410.preview_replace_timeline_dialogue,
        voice_m410.apply_replace_timeline_dialogue,
    ),
    "avatar.create_plan": MutationHandler(
        avatar_m412.preview_create_plan,
        avatar_m412.apply_create_plan,
    ),
    "avatar.create_job": MutationHandler(
        avatar_m412.preview_create_job,
        avatar_m412.apply_create_job,
    ),
    "avatar.adjust_section": MutationHandler(
        avatar_m412.preview_adjust_section,
        avatar_m412.apply_adjust_section,
    ),
    "avatar.request_retake": MutationHandler(
        avatar_m412.preview_request_retake,
        avatar_m412.apply_request_retake,
    ),
    "avatar.repair_lipsync": MutationHandler(
        avatar_m412.preview_repair_lipsync,
        avatar_m412.apply_repair_lipsync,
    ),
    "avatar.replace_voice": MutationHandler(
        avatar_m412.preview_replace_voice,
        avatar_m412.apply_replace_voice,
    ),
    "avatar.assemble": MutationHandler(
        avatar_m412.preview_assemble,
        avatar_m412.apply_assemble,
    ),
    "avatar.prepare_timeline": MutationHandler(
        avatar_m412.preview_prepare_timeline,
        avatar_m412.apply_prepare_timeline,
    ),
    "spatial.create_map": MutationHandler(
        spatial_m411.preview_create_map,
        spatial_m411.apply_create_map,
    ),
    "spatial.update_bounds": MutationHandler(
        spatial_m411.preview_update_bounds,
        spatial_m411.apply_update_bounds,
    ),
    "spatial.place_character": MutationHandler(
        spatial_m411.preview_place_character,
        spatial_m411.apply_place_character,
    ),
    "spatial.place_prop": MutationHandler(
        spatial_m411.preview_place_prop,
        spatial_m411.apply_place_prop,
    ),
    "spatial.move_placement": MutationHandler(
        spatial_m411.preview_move_placement,
        spatial_m411.apply_move_placement,
    ),
    "spatial.create_camera": MutationHandler(
        spatial_m411.preview_create_camera,
        spatial_m411.apply_create_camera,
    ),
    "spatial.update_camera": MutationHandler(
        spatial_m411.preview_update_camera,
        spatial_m411.apply_update_camera,
    ),
    "spatial.create_path": MutationHandler(
        spatial_m411.preview_create_path,
        spatial_m411.apply_create_path,
    ),
    "spatial.generate_360_plan": MutationHandler(
        spatial_m411.preview_generate_360_plan,
        spatial_m411.apply_generate_360_plan,
    ),
    "spatial.assign_to_scene": MutationHandler(
        spatial_m411.preview_assign_to_scene,
        spatial_m411.apply_assign_to_scene,
    ),
    "spatial.prepare_image_generation": MutationHandler(
        spatial_m411.preview_prepare_image_generation,
        spatial_m411.apply_prepare_image_generation,
    ),
    "spatial.prepare_video_generation": MutationHandler(
        spatial_m411.preview_prepare_video_generation,
        spatial_m411.apply_prepare_video_generation,
    ),
    "create_scene": MutationHandler(scenes.preview_create_scene, scenes.apply_create_scene),
    "update_scene_title": MutationHandler(scenes.preview_update_scene_title, scenes.apply_update_scene_title),
    "set_scene_prompt": MutationHandler(scenes.preview_set_scene_prompt, scenes.apply_set_scene_prompt),
    "prompt.apply_enhancement": MutationHandler(
        prompt_intelligence.preview_prompt_apply_enhancement,
        prompt_intelligence.apply_prompt_apply_enhancement,
    ),
    "prompt.benchmark_run": MutationHandler(
        prompt_intelligence.preview_prompt_benchmark_run,
        prompt_intelligence.apply_prompt_benchmark_run,
    ),
    "prompt.promote_strategy": MutationHandler(
        prompt_intelligence.preview_prompt_promote_strategy,
        prompt_intelligence.apply_prompt_promote_strategy,
    ),
    "prompt.rollback_strategy": MutationHandler(
        prompt_intelligence.preview_prompt_rollback_strategy,
        prompt_intelligence.apply_prompt_rollback_strategy,
    ),
    "record_director_decision": MutationHandler(
        bible_read.preview_record_director_decision, bible_read.apply_record_director_decision
    ),
    "record_production_decision": MutationHandler(
        project_decisions.preview_record_production_decision,
        project_decisions.apply_record_production_decision,
    ),
    "propose_character_update": MutationHandler(
        bible_domain.preview_propose_character_update, bible_domain.apply_propose_character_update
    ),
    "propose_canon_record": MutationHandler(
        bible_domain.preview_propose_canon_record, bible_domain.apply_propose_canon_record
    ),
    "propose_canon_supersession": MutationHandler(
        bible_domain.preview_propose_canon_supersession, bible_domain.apply_propose_canon_supersession
    ),
    "propose_continuity_update": MutationHandler(
        bible_domain.preview_propose_continuity_update, bible_domain.apply_propose_continuity_update
    ),
    "propose_reference_link": MutationHandler(
        bible_domain.preview_propose_reference_link, bible_domain.apply_propose_reference_link
    ),
    "propose_production_decision": MutationHandler(
        bible_domain.preview_propose_production_decision, bible_domain.apply_propose_production_decision
    ),
    "propose_visual_language_update": MutationHandler(
        bible_domain.preview_propose_visual_language_update, bible_domain.apply_propose_visual_language_update
    ),
    "propose_storyboard_generation": MutationHandler(
        storyboard.preview_propose_storyboard_generation, storyboard.apply_propose_storyboard_generation
    ),
    "propose_script_document": MutationHandler(
        generation_tools.preview_propose_script_document, generation_tools.apply_propose_script_document
    ),
    "runtime.preview_install": MutationHandler(
        docker_runtime_tools.preview_install, docker_runtime_tools.apply_install
    ),
    "runtime.install": MutationHandler(
        docker_runtime_tools.preview_install, docker_runtime_tools.apply_install
    ),
    "runtime.preview_update": MutationHandler(
        docker_runtime_tools.preview_update, docker_runtime_tools.apply_update
    ),
    "runtime.update": MutationHandler(
        docker_runtime_tools.preview_update, docker_runtime_tools.apply_update
    ),
    "runtime.preview_repair": MutationHandler(
        docker_runtime_tools.preview_repair, docker_runtime_tools.apply_repair
    ),
    "runtime.repair": MutationHandler(
        docker_runtime_tools.preview_repair, docker_runtime_tools.apply_repair
    ),
    "runtime.preview_uninstall": MutationHandler(
        docker_runtime_tools.preview_uninstall, docker_runtime_tools.apply_uninstall
    ),
    "runtime.uninstall": MutationHandler(
        docker_runtime_tools.preview_uninstall, docker_runtime_tools.apply_uninstall
    ),
    "runtime.start": MutationHandler(
        docker_runtime_tools.preview_start, docker_runtime_tools.apply_start
    ),
    "runtime.stop": MutationHandler(
        docker_runtime_tools.preview_stop, docker_runtime_tools.apply_stop
    ),
    "runtime.restart": MutationHandler(
        docker_runtime_tools.preview_restart, docker_runtime_tools.apply_restart
    ),
    "setup.approve_source": MutationHandler(
        setup_guided.preview_approve_source, setup_guided.apply_approve_source
    ),
    "setup.create_install_job": MutationHandler(
        setup_guided.preview_create_install_job, setup_guided.apply_create_install_job
    ),
    "setup.install_component": MutationHandler(
        setup_guided.preview_install_component, setup_guided.apply_install_component
    ),
    "setup.install_recipe": MutationHandler(
        setup_guided.preview_install_recipe, setup_guided.apply_install_recipe
    ),
    "setup.link_existing_runtime": MutationHandler(
        setup_guided.preview_link_existing_runtime, setup_guided.apply_link_existing_runtime
    ),
    "setup.repair_component": MutationHandler(
        setup_guided.preview_repair_component, setup_guided.apply_repair_component
    ),
    "setup.restart_runtime": MutationHandler(
        setup_guided.preview_restart_runtime, setup_guided.apply_restart_runtime
    ),
    "setup.verify_component": MutationHandler(
        setup_guided.preview_verify_component, setup_guided.apply_verify_component
    ),
    "setup.calibrate_component": MutationHandler(
        setup_guided.preview_calibrate_component, setup_guided.apply_calibrate_component
    ),
    "setup.certify_component": MutationHandler(
        setup_guided.preview_certify_component, setup_guided.apply_certify_component
    ),
    "setup.update_component": MutationHandler(
        setup_guided.preview_update_component, setup_guided.apply_update_component
    ),
    "setup.remove_component": MutationHandler(
        setup_guided.preview_remove_component, setup_guided.apply_remove_component
    ),
    "setup.archive_component": MutationHandler(
        setup_guided.preview_archive_component, setup_guided.apply_archive_component
    ),
    "setup.move_installation": MutationHandler(
        setup_guided.preview_move_installation, setup_guided.apply_move_installation
    ),
    "script.propose_insert": MutationHandler(
        scriptwriter_tools.preview_propose_insert, scriptwriter_tools.apply_propose_insert
    ),
    "script.propose_replace": MutationHandler(
        scriptwriter_tools.preview_propose_replace, scriptwriter_tools.apply_propose_replace
    ),
    "script.propose_delete": MutationHandler(
        scriptwriter_tools.preview_propose_delete, scriptwriter_tools.apply_propose_delete
    ),
    "script.propose_scene": MutationHandler(
        scriptwriter_tools.preview_propose_scene, scriptwriter_tools.apply_propose_scene
    ),
    "script.convert_outline_to_scenes": MutationHandler(
        scriptwriter_tools.preview_convert_outline, scriptwriter_tools.apply_convert_outline
    ),
    "script.sync_production_bible": MutationHandler(
        scriptwriter_tools.preview_sync_bible, scriptwriter_tools.apply_sync_bible
    ),
    "script.prepare_timeline": MutationHandler(
        scriptwriter_tools.preview_prepare_timeline, scriptwriter_tools.apply_prepare_timeline
    ),
    "propose_music_generate": MutationHandler(
        generation_tools.preview_propose_music_generate, generation_tools.apply_propose_music_generate
    ),
    "propose_sfx_generate": MutationHandler(
        generation_tools.preview_propose_sfx_generate, generation_tools.apply_propose_sfx_generate
    ),
    "audio.generate_music": MutationHandler(
        audio_studio_tools.preview_generate_music,
        audio_studio_tools.apply_generate_music,
    ),
    "audio.generate_sfx": MutationHandler(
        audio_studio_tools.preview_generate_sfx,
        audio_studio_tools.apply_generate_sfx,
    ),
    "audio.generate_ambience": MutationHandler(
        audio_studio_tools.preview_generate_ambience,
        audio_studio_tools.apply_generate_ambience,
    ),
    "audio.select_candidate": MutationHandler(
        audio_studio_tools.preview_select_candidate,
        audio_studio_tools.apply_select_candidate,
    ),
    "audio.approve_candidate": MutationHandler(
        audio_studio_tools.preview_approve_candidate,
        audio_studio_tools.apply_approve_candidate,
    ),
    "audio.place": MutationHandler(
        audio_studio_tools.preview_place,
        audio_studio_tools.apply_place,
    ),
    "audio.replace_clip": MutationHandler(
        audio_studio_tools.preview_replace_clip,
        audio_studio_tools.apply_replace_clip,
    ),
    "audio.cancel_batch": MutationHandler(
        audio_studio_tools.preview_cancel_batch,
        audio_studio_tools.apply_cancel_batch,
    ),
    "propose_image_upscale": MutationHandler(
        generation_tools.preview_propose_image_upscale, generation_tools.apply_propose_image_upscale
    ),
    "propose_background_remove": MutationHandler(
        generation_tools.preview_propose_background_remove, generation_tools.apply_propose_background_remove
    ),
    "propose_chroma_key": MutationHandler(
        generation_tools.preview_propose_chroma_key, generation_tools.apply_propose_chroma_key
    ),
    "propose_portrait_skin": MutationHandler(
        generation_tools.preview_propose_portrait_skin, generation_tools.apply_propose_portrait_skin
    ),
    "propose_video_upscale": MutationHandler(
        generation_tools.preview_propose_video_upscale, generation_tools.apply_propose_video_upscale
    ),
    "magi.color.apply": MutationHandler(magi.preview_color_apply, magi.apply_color_apply),
    "magi.upscale": MutationHandler(magi.preview_upscale, magi.apply_upscale),
    "magi.audio.generate": MutationHandler(magi.preview_audio_generate, magi.apply_audio_generate),
    "magi.render": MutationHandler(magi.preview_render, magi.apply_render),
    "propose_video_extend": MutationHandler(
        media_execution.preview_propose_video_extend_w6p,
        media_execution.apply_propose_video_extend_w6p,
    ),
    "propose_image_generate": MutationHandler(
        media_execution.preview_propose_image_generate,
        media_execution.apply_propose_image_generate,
    ),
    "propose_image_edit": MutationHandler(
        media_execution.preview_propose_image_edit,
        media_execution.apply_propose_image_edit,
    ),
    "propose_video_generate": MutationHandler(
        media_execution.preview_propose_video_generate,
        media_execution.apply_propose_video_generate,
    ),
    "propose_shot_generate": MutationHandler(
        media_execution.preview_propose_shot_generate,
        media_execution.apply_propose_shot_generate,
    ),
    "propose_scene_generate": MutationHandler(
        media_execution.preview_propose_scene_generate,
        media_execution.apply_propose_scene_generate,
    ),
    "propose_three_frame_generate": MutationHandler(
        media_execution.preview_propose_three_frame_generate,
        media_execution.apply_propose_three_frame_generate,
    ),
    "propose_timeline_render": MutationHandler(
        media_execution.preview_propose_timeline_render,
        media_execution.apply_propose_timeline_render,
    ),
    "propose_batch_timeline": MutationHandler(
        media_execution.preview_propose_batch_timeline,
        media_execution.apply_propose_batch_timeline,
    ),
    "propose_lipsync": MutationHandler(
        media_execution.preview_propose_lipsync,
        media_execution.apply_propose_lipsync,
    ),
    "propose_voice_generate": MutationHandler(
        media_execution.preview_propose_voice_generate,
        media_execution.apply_propose_voice_generate,
    ),
    "propose_subtitle_generate": MutationHandler(
        media_execution.preview_propose_subtitle_generate,
        media_execution.apply_propose_subtitle_generate,
    ),
    "editor.place_asset": MutationHandler(
        media_execution.preview_editor_place_asset,
        media_execution.apply_editor_place_asset,
    ),
    "job.cancel": MutationHandler(
        media_execution.preview_job_cancel,
        media_execution.apply_job_cancel,
    ),
    "job.retry": MutationHandler(
        media_execution.preview_job_retry,
        media_execution.apply_job_retry,
    ),
    "propose_brand_generate": MutationHandler(
        generation_tools.preview_propose_brand_generate, generation_tools.apply_propose_brand_generate
    ),
    "propose_vision_correction": MutationHandler(
        vision.preview_propose_vision_correction, vision.apply_propose_vision_correction
    ),
    "propose_asset_bible_link": MutationHandler(
        vision.preview_propose_asset_bible_link, vision.apply_propose_asset_bible_link
    ),
    "record_vision_review": MutationHandler(
        vision.preview_record_vision_review, vision.apply_record_vision_review
    ),
    "create_reference_set_proposal": MutationHandler(
        timeline_references.preview_create_reference_set_proposal,
        timeline_references.apply_create_reference_set_proposal,
    ),
    "propose_add_reference_binding": MutationHandler(
        timeline_references.preview_propose_add_reference_binding,
        timeline_references.apply_propose_add_reference_binding,
    ),
    "propose_remove_reference_binding": MutationHandler(
        timeline_references.preview_propose_remove_reference_binding,
        timeline_references.apply_propose_remove_reference_binding,
    ),
    "propose_update_reference_binding": MutationHandler(
        timeline_references.preview_propose_update_reference_binding,
        timeline_references.apply_propose_update_reference_binding,
    ),
    "propose_apply_reference_preset": MutationHandler(
        timeline_references.preview_propose_apply_reference_preset,
        timeline_references.apply_propose_apply_reference_preset,
    ),
    "propose_asset_library_assignment": MutationHandler(
        library.preview_propose_asset_library_assignment,
        library.apply_propose_asset_library_assignment,
    ),
    "production_plan.create_draft": MutationHandler(
        wave4_plans.preview_create_draft,
        wave4_plans.apply_create_draft,
    ),
    "production_plan.propose": MutationHandler(wave4_plans.preview_propose, wave4_plans.apply_propose),
    "production_plan.approve": MutationHandler(wave4_plans.preview_approve, wave4_plans.apply_approve),
    "production_plan.reject": MutationHandler(wave4_plans.preview_reject, wave4_plans.apply_reject),
    "production_plan.revise": MutationHandler(wave4_plans.preview_revise, wave4_plans.apply_revise),
    "production_plan.pause": MutationHandler(wave4_plans.preview_pause, wave4_plans.apply_pause),
    "production_plan.resume": MutationHandler(wave4_plans.preview_resume, wave4_plans.apply_resume),
    "production_plan.cancel": MutationHandler(wave4_plans.preview_cancel, wave4_plans.apply_cancel),
    "production_plan.archive": MutationHandler(wave4_plans.preview_archive, wave4_plans.apply_archive),
    "production_plan.resolve_blocker": MutationHandler(
        wave4_plans.preview_resolve_blocker,
        wave4_plans.apply_resolve_blocker,
    ),
    "continuity.propose_correction": MutationHandler(
        continuity_w5.preview_propose_correction,
        continuity_w5.apply_propose_correction,
    ),
    "references.attach": MutationHandler(
        scene_references_w6p.preview_attach,
        scene_references_w6p.apply_attach,
    ),
    "references.update": MutationHandler(
        scene_references_w6p.preview_update,
        scene_references_w6p.apply_update,
    ),
    "references.remove": MutationHandler(
        scene_references_w6p.preview_remove,
        scene_references_w6p.apply_remove,
    ),
    "references.copy": MutationHandler(
        scene_references_w6p.preview_copy,
        scene_references_w6p.apply_copy,
    ),
    "timeline.set_playhead": MutationHandler(
        director_timeline_tools.preview_set_playhead,
        director_timeline_tools.apply_set_playhead,
    ),
    "timeline.update_settings": MutationHandler(
        director_timeline_tools.preview_update_settings,
        director_timeline_tools.apply_update_settings,
    ),
    "timeline.set_guidance_priority": MutationHandler(
        director_timeline_tools.preview_set_guidance_priority,
        director_timeline_tools.apply_set_guidance_priority,
    ),
    "timeline.remove_item": MutationHandler(
        director_timeline_tools.preview_remove_item,
        director_timeline_tools.apply_remove_item,
    ),
    "timeline.restore_removed_item": MutationHandler(
        director_timeline_tools.preview_restore_removed_item,
        director_timeline_tools.apply_restore_removed_item,
    ),
    "timeline.propose_add_batch": MutationHandler(
        director_timeline_tools.preview_propose_add_batch,
        director_timeline_tools.apply_propose_add_batch,
    ),
    "timeline.propose_add_image_clip": MutationHandler(
        director_timeline_tools.preview_propose_add_image_clip,
        director_timeline_tools.apply_propose_add_image_clip,
    ),
    "timeline.propose_add_prompt_segment": MutationHandler(
        director_timeline_tools.preview_propose_add_prompt_segment,
        director_timeline_tools.apply_propose_add_prompt_segment,
    ),
    "timeline.build_shot": MutationHandler(
        director_timeline_tools.preview_build_shot,
        director_timeline_tools.apply_build_shot,
    ),
    "timeline.propose_add_camera": MutationHandler(
        director_timeline_tools.preview_propose_add_camera,
        director_timeline_tools.apply_propose_add_camera,
    ),
    "timeline.propose_update_camera": MutationHandler(
        director_timeline_tools.preview_propose_update_camera,
        director_timeline_tools.apply_propose_update_camera,
    ),
    "timeline.propose_layout_preset": MutationHandler(
        director_timeline_tools.preview_propose_layout_preset,
        director_timeline_tools.apply_propose_layout_preset,
    ),
    "timeline.propose_viewer_fullscreen": MutationHandler(
        director_timeline_tools.preview_propose_viewer_fullscreen,
        director_timeline_tools.apply_propose_viewer_fullscreen,
    ),
    "timeline.propose_layout_reset": MutationHandler(
        director_timeline_tools.preview_propose_layout_reset,
        director_timeline_tools.apply_propose_layout_reset,
    ),
    "timeline.propose_zoom": MutationHandler(
        director_timeline_tools.preview_propose_zoom,
        director_timeline_tools.apply_propose_zoom,
    ),
    "timeline.propose_add_lipsync_track": MutationHandler(
        director_timeline_tools.preview_propose_add_lipsync_track,
        director_timeline_tools.apply_propose_add_lipsync_track,
    ),
    "timeline.propose_remove_lipsync_track": MutationHandler(
        director_timeline_tools.preview_propose_remove_lipsync_track,
        director_timeline_tools.apply_propose_remove_lipsync_track,
    ),
    "timeline.propose_add_lipsync_clip": MutationHandler(
        director_timeline_tools.preview_propose_add_lipsync_clip,
        director_timeline_tools.apply_propose_add_lipsync_clip,
    ),
    "timeline.propose_bind_lipsync_clip": MutationHandler(
        director_timeline_tools.preview_propose_bind_lipsync_clip,
        director_timeline_tools.apply_propose_bind_lipsync_clip,
    ),
    "timeline.propose_open_inpaint": MutationHandler(
        director_timeline_tools.preview_propose_open_inpaint,
        director_timeline_tools.apply_propose_open_inpaint,
    ),
    "timeline.propose_create_inpaint_mask": MutationHandler(
        director_timeline_tools.preview_propose_create_inpaint_mask,
        director_timeline_tools.apply_propose_create_inpaint_mask,
    ),
    "timeline.propose_execute_inpaint": MutationHandler(
        director_timeline_tools.preview_propose_execute_inpaint,
        director_timeline_tools.apply_propose_execute_inpaint,
    ),
    "timeline.propose_approve_inpaint": MutationHandler(
        director_timeline_tools.preview_propose_approve_inpaint,
        director_timeline_tools.apply_propose_approve_inpaint,
    ),
    "timeline.propose_restore_inpaint": MutationHandler(
        director_timeline_tools.preview_propose_restore_inpaint,
        director_timeline_tools.apply_propose_restore_inpaint,
    ),
    "timeline.propose_generate_scene": MutationHandler(
        director_timeline_tools.preview_propose_generate_scene,
        director_timeline_tools.apply_propose_generate_scene,
    ),
    "timeline.propose_repair_range": MutationHandler(
        director_timeline_tools.preview_propose_repair_range,
        director_timeline_tools.apply_propose_repair_range,
    ),
    "timeline.propose_cancel": MutationHandler(
        director_timeline_tools.preview_propose_cancel,
        director_timeline_tools.apply_propose_cancel,
    ),
    "timeline.propose_retake": MutationHandler(
        director_timeline_tools.preview_propose_retake,
        director_timeline_tools.apply_propose_retake,
    ),
    "timeline.attach_optional_reference": MutationHandler(
        director_timeline_tools.preview_attach_optional_reference,
        director_timeline_tools.apply_attach_optional_reference,
    ),
    "image_pipeline.prepare_plan": MutationHandler(
        image_pipeline_tools.preview_prepare_plan,
        image_pipeline_tools.apply_prepare_plan,
    ),
    "image_pipeline.prepare_creative_direction": MutationHandler(
        image_pipeline_tools.preview_prepare_creative_direction,
        image_pipeline_tools.apply_prepare_creative_direction,
    ),
    "image_pipeline.select_profile": MutationHandler(
        image_pipeline_tools.preview_select_profile,
        image_pipeline_tools.apply_select_profile,
    ),
    "image_pipeline.assign_reference": MutationHandler(
        image_pipeline_tools.preview_assign_reference,
        image_pipeline_tools.apply_assign_reference,
    ),
    "image_pipeline.load_spatial_map": MutationHandler(
        image_pipeline_tools.preview_load_spatial_map,
        image_pipeline_tools.apply_load_spatial_map,
    ),
    "image_pipeline.prepare_posecraft": MutationHandler(
        image_pipeline_tools.preview_prepare_posecraft,
        image_pipeline_tools.apply_prepare_posecraft,
    ),
    "image_pipeline.generate_candidates": MutationHandler(
        image_pipeline_tools.preview_generate_candidates,
        image_pipeline_tools.apply_generate_candidates,
    ),
    "image_pipeline.evaluate_candidates": MutationHandler(
        image_pipeline_tools.preview_evaluate_candidates,
        image_pipeline_tools.apply_evaluate_candidates,
    ),
    "image_pipeline.recommend_candidate": MutationHandler(
        image_pipeline_tools.preview_recommend_candidate,
        image_pipeline_tools.apply_recommend_candidate,
    ),
    "image_pipeline.select_candidate": MutationHandler(
        image_pipeline_tools.preview_select_candidate,
        image_pipeline_tools.apply_select_candidate,
    ),
    "image_pipeline.prepare_repair": MutationHandler(
        image_pipeline_tools.preview_prepare_repair,
        image_pipeline_tools.apply_prepare_repair,
    ),
    "image_pipeline.apply_repair": MutationHandler(
        image_pipeline_tools.preview_apply_repair,
        image_pipeline_tools.apply_apply_repair,
    ),
    "image_pipeline.master": MutationHandler(
        image_pipeline_tools.preview_master,
        image_pipeline_tools.apply_master,
    ),
    "image_pipeline.approve": MutationHandler(
        image_pipeline_tools.preview_approve,
        image_pipeline_tools.apply_approve,
    ),
    "image_pipeline.cancel": MutationHandler(
        image_pipeline_tools.preview_cancel,
        image_pipeline_tools.apply_cancel,
    ),
    "multi_shot.create_plan": MutationHandler(
        multi_shot_tools.preview_create_plan,
        multi_shot_tools.apply_create_plan,
    ),
    "multi_shot.add_shots": MutationHandler(
        multi_shot_tools.preview_add_shots,
        multi_shot_tools.apply_add_shots,
    ),
    "multi_shot.send_to_timeline": MutationHandler(
        multi_shot_tools.preview_send_to_timeline,
        multi_shot_tools.apply_send_to_timeline,
    ),
    # CDX-033: legacy ers.* 4-direction chat mutation tools are INERT - they
    # stay registered so definitions.py closure validation passes, but
    # exposure.py never surfaces them to the model (chat 'generate the ERS'
    # routes to the ers.generate capability).
    "ers.create_sheet": MutationHandler(
        environment_reference_sheet.preview_create_sheet,
        environment_reference_sheet.apply_create_sheet,
    ),
    "ers.attach_spatial_map": MutationHandler(
        environment_reference_sheet.preview_attach_spatial_map,
        environment_reference_sheet.apply_attach_spatial_map,
    ),
    "ers.generate_directional_views": MutationHandler(
        environment_reference_sheet.preview_generate_directional_views,
        environment_reference_sheet.apply_generate_directional_views,
    ),
    "ers.approve_direction": MutationHandler(
        environment_reference_sheet.preview_approve_direction,
        environment_reference_sheet.apply_approve_direction,
    ),
    "ers.validate_continuity": MutationHandler(
        environment_reference_sheet.preview_validate_continuity,
        environment_reference_sheet.apply_validate_continuity,
    ),
    "ers.compose_sheet": MutationHandler(
        environment_reference_sheet.preview_compose_sheet,
        environment_reference_sheet.apply_compose_sheet,
    ),
    "ers.register_project": MutationHandler(
        environment_reference_sheet.preview_register_project,
        environment_reference_sheet.apply_register_project,
    ),
    "ers.set_optional_three_d": MutationHandler(
        environment_reference_sheet.preview_set_optional_three_d,
        environment_reference_sheet.apply_set_optional_three_d,
    ),
    "ers.export_sheet": MutationHandler(
        environment_reference_sheet.preview_export_sheet,
        environment_reference_sheet.apply_export_sheet,
    ),
    "minimax_h3.prepare_plan": MutationHandler(
        minimax_h3_tools.preview_prepare_plan,
        minimax_h3_tools.apply_prepare_plan,
    ),
    "minimax_h3.prepare_three_frame": MutationHandler(
        minimax_h3_tools.preview_prepare_three_frame,
        minimax_h3_tools.apply_prepare_three_frame,
    ),
    "minimax_h3.request_generation": MutationHandler(
        minimax_h3_tools.preview_request_generation,
        minimax_h3_tools.apply_request_generation,
    ),
    "minimax_h3.offer_ltx_fallback": MutationHandler(
        minimax_h3_tools.preview_offer_ltx_fallback,
        minimax_h3_tools.apply_offer_ltx_fallback,
    ),
    "minimax_h3.accept_ltx_fallback": MutationHandler(
        minimax_h3_tools.preview_accept_ltx_fallback,
        minimax_h3_tools.apply_accept_ltx_fallback,
    ),
    "minimax_h3.cancel": MutationHandler(
        minimax_h3_tools.preview_cancel,
        minimax_h3_tools.apply_cancel,
    ),
    "minimax_h3.retry": MutationHandler(
        minimax_h3_tools.preview_retry,
        minimax_h3_tools.apply_retry,
    ),
    "posecraft.create_scene": MutationHandler(
        posecraft.preview_create_scene, posecraft.apply_create_scene
    ),
    "posecraft.add_figure": MutationHandler(
        posecraft.preview_add_figure, posecraft.apply_add_figure
    ),
    "posecraft.rename_object": MutationHandler(
        posecraft.preview_rename_object, posecraft.apply_rename_object
    ),
    "posecraft.set_figure_role": MutationHandler(
        posecraft.preview_set_figure_role, posecraft.apply_set_figure_role
    ),
    "posecraft.map_character": MutationHandler(
        posecraft.preview_map_character, posecraft.apply_map_character
    ),
    "posecraft.set_figure_color": MutationHandler(
        posecraft.preview_set_figure_color, posecraft.apply_set_figure_color
    ),
    "posecraft.apply_pose": MutationHandler(
        posecraft.preview_apply_pose, posecraft.apply_apply_pose
    ),
    "posecraft.update_figure_transform": MutationHandler(
        posecraft.preview_update_figure_transform, posecraft.apply_update_figure_transform
    ),
    "posecraft.set_eyeline": MutationHandler(
        posecraft.preview_set_eyeline, posecraft.apply_set_eyeline
    ),
    "posecraft.set_camera": MutationHandler(
        posecraft.preview_set_camera, posecraft.apply_set_camera
    ),
    "posecraft.save_scene": MutationHandler(
        posecraft.preview_save_scene, posecraft.apply_save_scene
    ),
    "posecraft.send_to_image_pipeline": MutationHandler(
        posecraft.preview_send_to_image_pipeline, posecraft.apply_send_to_image_pipeline
    ),
    "posecraft.send_to_storyboard": MutationHandler(
        posecraft.preview_send_to_storyboard, posecraft.apply_send_to_storyboard
    ),
}

_BY_ID: dict[str, ToolDefinition] = {t.tool_id: t for t in TOOL_DEFINITIONS}


def _validate_bindings() -> None:
    """Fail at import time rather than mid-turn if the registry is internally inconsistent."""

    for definition in TOOL_DEFINITIONS:
        bound = _READ_HANDLERS if definition.kind == "read" else _MUTATION_HANDLERS
        if definition.tool_id not in bound:
            raise RuntimeError(f"Tool '{definition.tool_id}' is declared but has no {definition.kind} handler.")
    unknown = (set(_READ_HANDLERS) | set(_MUTATION_HANDLERS)) - set(_BY_ID)
    if unknown:
        raise RuntimeError(f"Handlers bound for undeclared tools: {sorted(unknown)}")


_validate_bindings()


def all_definitions() -> tuple[ToolDefinition, ...]:
    return TOOL_DEFINITIONS


def get_definitions(tool_ids: list[str]) -> list[ToolDefinition]:
    """Resolve a curated list of tool IDs to their definitions.

    Unknown IDs are skipped (not raised) — callers curating a tool catalog
    should not crash the turn because one ID drifted. Used by the unified
    intent dispatcher to inject a compact tool catalog into the LLM prompt.
    """
    out: list[ToolDefinition] = []
    seen: set[str] = set()
    for tid in tool_ids or []:
        if not tid or tid in seen:
            continue
        resolved = resolve_tool_id(tid)
        definition = _BY_ID.get(tid) or _BY_ID.get(resolved)
        if definition is None:
            continue
        seen.add(tid)
        out.append(definition)
    return out


def catalog() -> list[dict[str, Any]]:
    return [t.to_dict() for t in TOOL_DEFINITIONS]


def get(tool_id: str) -> ToolDefinition:
    resolved = resolve_tool_id(tool_id)
    definition = _BY_ID.get(tool_id) or _BY_ID.get(resolved)
    if definition is None:
        raise CoDirectorError(
            TOOL_NOT_FOUND,
            f"'{tool_id}' isn't a Co-Director tool.",
            details={"toolId": tool_id},
            recoverable=False,
            recommended_action="none",
        )
    return definition


def get_tool_definition(tool_id: str) -> ToolDefinition:
    return get(tool_id)


def find(tool_id: str) -> Optional[ToolDefinition]:
    resolved = resolve_tool_id(tool_id)
    return _BY_ID.get(tool_id) or _BY_ID.get(resolved)


def require_kind(tool_id: str, kind: str) -> ToolDefinition:
    definition = get(tool_id)
    if definition.kind != kind:
        raise CoDirectorError(
            TOOL_KIND_MISMATCH,
            (
                f"'{tool_id}' is a {definition.kind} tool and can't be used here."
                if definition.kind == "read"
                else f"'{tool_id}' changes project data, so it needs an approved proposal."
            ),
            details={"toolId": tool_id, "kind": definition.kind, "expectedKind": kind},
            recoverable=False,
            recommended_action="none",
        )
    return definition


def check_schema_version(definition: ToolDefinition, version: int) -> None:
    """Guard a stored proposal against a registry that has since changed shape."""

    if version != definition.schema_version:
        raise CoDirectorError(
            TOOL_SCHEMA_VERSION_MISMATCH,
            "This proposal was created for an older version of the tool and can't be applied.",
            details={
                "toolId": definition.tool_id,
                "proposalSchemaVersion": version,
                "currentSchemaVersion": definition.schema_version,
            },
            recoverable=False,
            recommended_action="none",
        )


def read_handler(tool_id: str) -> ReadHandler:
    require_kind(tool_id, "read")
    return _READ_HANDLERS[tool_id]


def mutation_handler(tool_id: str) -> MutationHandler:
    require_kind(tool_id, "mutating")
    return _MUTATION_HANDLERS[tool_id]
