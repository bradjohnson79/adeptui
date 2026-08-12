"""Build + validate + fingerprint-check graphs for QueueWorker execute-only path."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from .certified_registry import get_workflow
from .fingerprints import (
    WorkflowGraphDriftError,
    assert_no_graph_drift,
    assert_no_topology_drift,
    graph_hash,
    topology_hash,
    validate_dynamic_bindings,
)
from .graph_validation import assert_graph_valid
from .workflow_resolver import CanonicalWorkflowContract

logger = logging.getLogger(__name__)


def _emit_fingerprint_evidence(line: str) -> None:
    """Emit the fingerprint-path evidence line to the app logger AND stdout.

    stdout is timestamped into the Beta api.log by the supervisor pump (the API
    has no logging.basicConfig, so INFO records would otherwise be dropped) —
    this is the same pattern the generation watcher uses for its evidence trail.
    """
    logger.info("%s", line)
    print(line, flush=True)


def build_leaf_graph(
    contract: CanonicalWorkflowContract,
    *,
    settings: Any,
    positive: str,
    negative: str,
    width: int,
    height: int,
    length: int,
    fps: int,
    seed: int,
    start_image: Optional[str] = None,
    middle_image: Optional[str] = None,
    end_image: Optional[str] = None,
    audio_file: Optional[str] = None,
    steps: int = 8,
    filename_prefix: str = "studio/render",
    wan_segment: str = "start_mid",
    video_path: Optional[str] = None,
    audio_path: Optional[str] = None,
) -> dict[str, Any]:
    key = contract.leaf_workflow_key

    if key == "wan.first_last_frame":
        from ..workflows.wan_builder import build_wan_flf_workflow

        return build_wan_flf_workflow(
            high_noise=settings.wan_high_noise,
            low_noise=settings.wan_low_noise,
            vae_name=settings.wan_vae,
            text_encoder=settings.wan_text_encoder,
            positive=positive,
            negative=negative,
            width=width,
            height=height,
            length=length,
            fps=fps,
            seed=seed,
            start_image=start_image,
            end_image=end_image or middle_image,
            steps_high=max(2, steps // 2),
            steps_low=max(2, steps // 2),
            filename_prefix=filename_prefix,
        )

    if key == "wan.three_frame":
        from ..workflows.wan_builder import build_wan_three_frame_workflow

        if not (start_image and middle_image and end_image):
            raise RuntimeError("wan.three_frame requires start, middle, and end frames")
        return build_wan_three_frame_workflow(
            high_noise=settings.wan_high_noise,
            low_noise=settings.wan_low_noise,
            vae_name=settings.wan_vae,
            text_encoder=settings.wan_text_encoder,
            positive=positive,
            negative=negative,
            width=width,
            height=height,
            length=length,
            fps=fps,
            seed=seed,
            start_image=start_image,
            middle_image=middle_image,
            end_image=end_image,
            segment=wan_segment,
            steps_high=max(2, steps // 2),
            steps_low=max(2, steps // 2),
            filename_prefix=filename_prefix,
        )

    if key == "ltx.simple_i2v":
        from ..workflows.ltx_builder import build_ltx_simple_i2v

        if not start_image:
            raise RuntimeError("ltx.simple_i2v requires start_image")
        return build_ltx_simple_i2v(
            checkpoint=settings.ltx_checkpoint,
            positive=positive,
            negative=negative,
            width=width,
            height=height,
            length=length,
            fps=fps,
            seed=seed,
            start_image=start_image,
            steps=steps,
            filename_prefix=filename_prefix,
            text_encoder=settings.ltx_text_encoder,
        )

    if key == "ltx.scene":
        from ..workflows.ltx_builder import build_ltx_scene_workflow

        return build_ltx_scene_workflow(
            checkpoint=settings.ltx_checkpoint,
            positive=positive,
            negative=negative,
            width=width,
            height=height,
            length=length,
            fps=fps,
            seed=seed,
            start_image=start_image,
            middle_image=middle_image,
            end_image=end_image,
            audio_file=audio_file,
            steps=steps,
            filename_prefix=filename_prefix,
            text_encoder=settings.ltx_text_encoder,
        )

    if key == "lipsync.latentsync":
        from ..workflows.lipsync_builder import build_latentsync_workflow

        if not video_path or not audio_path:
            raise RuntimeError("lipsync.latentsync requires video_path and audio_path")
        return build_latentsync_workflow(video_path=video_path, audio_path=audio_path)

    if key in {"hunyuan15.t2v", "hunyuan15.i2v", "hunyuan13b.t2v", "hunyuan13b.i2v"}:
        from .hunyuan_providers import HUNYUAN_13B, HUNYUAN_15, load_install_status, provider_dir

        provider_id = HUNYUAN_15 if key.startswith("hunyuan15") else HUNYUAN_13B
        model_root = str(provider_dir(provider_id))
        profile = (load_install_status(provider_id).get("profile") or "fp8_production")
        if key == "hunyuan15.t2v":
            from ..workflows.hunyuan15_builder import build_hunyuan15_t2v

            return build_hunyuan15_t2v(
                model_root=model_root,
                positive=positive,
                negative=negative,
                width=width,
                height=height,
                length=length,
                fps=fps,
                seed=seed,
                steps=max(steps, 20),
                filename_prefix=filename_prefix,
            )
        if key == "hunyuan15.i2v":
            from ..workflows.hunyuan15_builder import build_hunyuan15_i2v

            if not start_image:
                raise RuntimeError("hunyuan15.i2v requires start_image")
            return build_hunyuan15_i2v(
                model_root=model_root,
                positive=positive,
                negative=negative,
                start_image=start_image,
                width=width,
                height=height,
                length=length,
                fps=fps,
                seed=seed,
                steps=max(steps, 20),
                filename_prefix=filename_prefix,
            )
        if key == "hunyuan13b.t2v":
            from ..workflows.hunyuan13b_builder import build_hunyuan13b_t2v

            return build_hunyuan13b_t2v(
                model_root=model_root,
                positive=positive,
                negative=negative,
                width=width,
                height=height,
                length=length,
                fps=fps,
                seed=seed,
                steps=max(steps, 30),
                profile=str(profile),
                filename_prefix=filename_prefix,
            )
        from ..workflows.hunyuan13b_builder import build_hunyuan13b_i2v

        if not start_image:
            raise RuntimeError("hunyuan13b.i2v requires start_image")
        return build_hunyuan13b_i2v(
            model_root=model_root,
            positive=positive,
            negative=negative,
            start_image=start_image,
            width=width,
            height=height,
            length=length,
            fps=fps,
            seed=seed,
            steps=max(steps, 30),
            profile=str(profile),
            filename_prefix=filename_prefix,
        )

    if key.startswith("ltx_25."):
        from ..workflows.ltx_25_builder import (
            build_ltx_25_i2v,
            build_ltx_25_t2v,
        )

        length_seconds = length / float(fps) if fps > 0 else 5.0
        generate_audio = audio_file is not None
        fast_mode = steps <= 16

        if key == "ltx_25.t2v":
            return build_ltx_25_t2v(
                settings=settings,
                execution_id=filename_prefix.split("/")[-1] if "/" in filename_prefix else filename_prefix,
                prompt=positive,
                negative_prompt=negative,
                width=width,
                height=height,
                length_seconds=length_seconds,
                fps=fps,
                seed=seed,
                generate_audio=generate_audio,
                fast_mode=fast_mode,
            )

        if key == "ltx_25.i2v":
            if not start_image:
                raise RuntimeError("ltx_25.i2v requires start_image")
            return build_ltx_25_i2v(
                settings=settings,
                execution_id=filename_prefix.split("/")[-1] if "/" in filename_prefix else filename_prefix,
                prompt=positive,
                negative_prompt=negative,
                start_image_path=start_image,
                width=width,
                height=height,
                length_seconds=length_seconds,
                fps=fps,
                seed=seed,
                generate_audio=generate_audio,
                fast_mode=fast_mode,
            )

        raise RuntimeError(f"Unknown ltx_25 leaf workflow: {key}")

    raise RuntimeError(f"No local Comfy builder for leaf workflow: {key}")


def prepare_executable_graph(
    contract: CanonicalWorkflowContract,
    graph: Mapping[str, Any],
    *,
    enforce_certified_fingerprint: bool = True,
) -> dict[str, Any]:
    """Static-validate and fingerprint-check before queue_prompt.

    Canonical fingerprint contract: when the certified entry carries
    ``fingerprints.topologyHash``, topology is the drift gate (structure only —
    per-job bindings like prompt/seed/frames/fps/geometry/steps legitimately
    vary per Timeline batch). Legacy ``graphHash`` remains the gate only for
    unmigrated entries. Dynamic bindings are always validated (fail fast).
    """
    leaf = get_workflow(contract.leaf_workflow_key)
    assert_graph_valid(dict(graph), workflow_key=contract.leaf_workflow_key)
    bindings = validate_dynamic_bindings(graph)
    if not bindings["ok"]:
        _emit_fingerprint_evidence(
            f"workflowFingerprint workflow={contract.leaf_workflow_key}@{contract.leaf_workflow_version} "
            f"registryEntry={str(leaf is not None).lower()} selectedPath=none "
            f"bindingsValid=false bindingsErrors=\"{'; '.join(bindings['errors'])}\""
        )
        raise RuntimeError(
            f"Dynamic bindings invalid for {contract.leaf_workflow_key}: "
            + "; ".join(bindings["errors"])
        )
    expected_topology = leaf.fingerprints.topology_hash if leaf else None
    expected_legacy = None
    if leaf and leaf.fingerprints.graph_hash:
        expected_legacy = leaf.fingerprints.graph_hash
    elif contract.fingerprint_expected.get("graphHash"):
        expected_legacy = contract.fingerprint_expected.get("graphHash")

    # Decide which fingerprint gate (if any) applies, and why — then log it so a
    # live drift failure always explains its own hash-path selection.
    selected = "none"
    reason = ""
    if leaf and leaf.status == "Certified" and enforce_certified_fingerprint:
        if expected_topology:
            selected = "topology"
        elif expected_legacy:
            selected = "legacy"
            reason = "registry entry has no fingerprints.topologyHash"
        else:
            reason = "certified entry carries neither topologyHash nor graphHash"
    elif not leaf:
        reason = "workflow not present in certified registry"
    elif leaf.status != "Certified":
        reason = f"registry status={leaf.status} (drift gate applies to Certified only)"
    else:
        reason = "enforce_certified_fingerprint=False"

    actual_topology = topology_hash(graph) if selected == "topology" else None
    actual_legacy = graph_hash(graph) if selected == "legacy" else None
    _emit_fingerprint_evidence(
        f"workflowFingerprint workflow={contract.leaf_workflow_key}@{contract.leaf_workflow_version} "
        f"registryEntry={str(leaf is not None).lower()} "
        f"topologyHashCertified={str(bool(expected_topology)).lower()} "
        f"legacyGraphHashCertified={str(bool(expected_legacy)).lower()} "
        f"selectedPath={selected} "
        f"topologyMatch={str(actual_topology == expected_topology).lower() if selected == 'topology' else 'n/a'} "
        f"bindingsValid=true "
        f"legacyGraphHashCheck={str(selected == 'legacy').lower()} "
        f"reason=\"{reason}\" "
        f"certifiedTopology={expected_topology} actualTopology={actual_topology} "
        f"certifiedGraph={expected_legacy if selected == 'legacy' else None} actualGraph={actual_legacy}"
    )

    # Enforce drift only for Certified workflows (Blocked may carry provisional hashes).
    if selected == "topology":
        assert_no_topology_drift(
            built_graph=graph,
            expected_topology_hash=expected_topology,
            workflow_key=contract.leaf_workflow_key,
            workflow_version=contract.leaf_workflow_version,
        )
    elif selected == "legacy":
        try:
            assert_no_graph_drift(
                built_graph=graph,
                expected_graph_hash=expected_legacy,
                workflow_key=contract.leaf_workflow_key,
                workflow_version=contract.leaf_workflow_version,
            )
        except WorkflowGraphDriftError as exc:
            raise WorkflowGraphDriftError(
                f"{exc} | legacy graphHash selected because: {reason}",
                expected=expected_legacy,
                actual=actual_legacy,
            ) from exc
    return dict(graph)
