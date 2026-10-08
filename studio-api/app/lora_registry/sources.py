"""Authoritative LoRA source resolver.

Hugging Face and Civitai page URLs are resolved here. The UI does not parse
provider URLs. Additional providers can register a parser later.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from .metadata import family_from_base_model

HF_HOSTS = {"huggingface.co", "www.huggingface.co", "hf.co"}
CIVITAI_HOSTS = {"civitai.com", "www.civitai.com"}


@dataclass
class LoraSourceFile:
    filename: str
    size_bytes: int | None = None
    sha256: str = ""
    download_url: str = ""
    repo_id: str = ""
    revision: str = ""


@dataclass
class LoraSourceResolution:
    provider: str
    display_name: str = ""
    source_url: str = ""
    source_model_id: str = ""
    source_version: str = ""
    files: list[LoraSourceFile] = field(default_factory=list)
    selected: LoraSourceFile | None = None
    license: str = ""
    author: str = ""
    base_model: str = ""
    family: str = ""
    trigger_words: list[str] = field(default_factory=list)
    recommended_strength: float | None = None
    needs_token: bool = False
    token_provider: str = ""
    message: str = ""
    detail: str = ""

    def public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["files"] = [asdict(item) for item in self.files]
        payload["selected"] = asdict(self.selected) if self.selected else None
        return payload


def _token(secret_name: str, env_keys: tuple[str, ...]) -> str:
    try:
        from ..secrets_store import get_secret

        stored = (get_secret(secret_name) or "").strip()
        if stored:
            return stored
    except Exception:
        pass
    for key in env_keys:
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    return ""


def huggingface_token() -> str:
    return _token("hf_token", ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "ADEPT_HF_TOKEN"))


def civitai_token() -> str:
    return _token("civitai_api_token", ("CIVITAI_API_TOKEN", "CIVITAI_TOKEN"))


def token_configured() -> dict[str, bool]:
    return {"huggingface": bool(huggingface_token()), "civitai": bool(civitai_token())}


def _split_hf_path(path: str) -> tuple[str, str, str, str]:
    """Return repo_id, revision, file path, kind (repo|file|tree)."""
    parts = [unquote(part) for part in path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("Paste a Hugging Face model page or a file link.")
    repo_id = f"{parts[0]}/{parts[1]}"
    if len(parts) == 2:
        return repo_id, "", "", "repo"
    kind = parts[2]
    if kind not in {"blob", "resolve", "tree"} or len(parts) < 4:
        return repo_id, "", "", "repo"
    revision = parts[3]
    file_path = "/".join(parts[4:])
    if kind == "tree" and not file_path:
        return repo_id, revision, "", "tree"
    if kind in {"blob", "resolve"} and file_path:
        return repo_id, revision, file_path, "file"
    if kind == "tree" and file_path:
        return repo_id, revision, file_path, "tree"
    return repo_id, revision, "", "repo"


def parse_lora_url(url: str) -> dict[str, str]:
    raw = str(url or "").strip()
    if not raw:
        raise ValueError("Paste a LoRA link first.")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower().split(":")[0]
    if host in HF_HOSTS:
        repo_id, revision, file_path, kind = _split_hf_path(parsed.path)
        return {
            "provider": "huggingface",
            "repo_id": repo_id,
            "revision": revision,
            "file_path": file_path,
            "kind": kind,
            "source_url": raw,
        }
    if host in CIVITAI_HOSTS:
        parts = [part for part in parsed.path.split("/") if part]
        model_id = ""
        version_id = ""
        if len(parts) >= 2 and parts[0] == "models" and parts[1].isdigit():
            model_id = parts[1]
        elif len(parts) >= 4 and parts[0] == "api" and parts[1] == "download" and parts[2] == "models" and parts[3].isdigit():
            version_id = parts[3]
        query = parsed.query or ""
        match = re.search(r"(?:^|&)modelVersionId=(\d+)", query)
        if match:
            version_id = match.group(1)
        if not model_id and not version_id:
            raise ValueError("Paste a Civitai model page. Adept UI could not find the model on that link.")
        return {
            "provider": "civitai",
            "model_id": model_id,
            "version_id": version_id,
            "source_url": raw,
        }
    raise ValueError("Paste a Hugging Face or Civitai LoRA link. Other sites can be added later.")


def _select_file(files: list[LoraSourceFile], preferred: str) -> LoraSourceFile | None:
    safes = [item for item in files if item.filename.lower().endswith(".safetensors")]
    if preferred:
        preferred_name = preferred.replace("\\", "/").split("/")[-1].lower()
        for item in safes:
            if item.filename.replace("\\", "/").lower() == preferred.lower() or item.filename.lower() == preferred_name:
                return item
    if len(safes) == 1:
        return safes[0]
    return None


def _hf_siblings(info: Any) -> list[LoraSourceFile]:
    files: list[LoraSourceFile] = []
    siblings = getattr(info, "siblings", None) or []
    revision = str(getattr(info, "sha", None) or getattr(info, "id", None) or "")
    repo_id = str(getattr(info, "id", None) or "")
    for sibling in siblings:
        name = str(getattr(sibling, "rfilename", None) or "")
        if not name.lower().endswith(".safetensors"):
            continue
        lfs = getattr(sibling, "lfs", None)
        sha = ""
        size = None
        if isinstance(lfs, dict):
            sha = str(lfs.get("sha256") or "")
            size = lfs.get("size")
        else:
            sha = str(getattr(lfs, "sha256", "") or "")
            size = getattr(lfs, "size", None)
        try:
            size_int = int(size) if size is not None else None
        except (TypeError, ValueError):
            size_int = None
        files.append(
            LoraSourceFile(
                filename=name,
                size_bytes=size_int,
                sha256=sha,
                repo_id=repo_id,
                revision=revision,
            )
        )
    return files


def _resolve_huggingface(parsed: dict[str, str], *, hf_info: Callable | None = None) -> LoraSourceResolution:
    token = huggingface_token()
    repo_id = parsed["repo_id"]
    revision = parsed.get("revision") or None
    result = LoraSourceResolution(
        provider="huggingface",
        source_url=parsed["source_url"],
        source_model_id=repo_id,
        source_version=parsed.get("revision") or "",
        display_name=repo_id.split("/")[-1],
        token_provider="huggingface",
    )
    try:
        if hf_info is not None:
            info = hf_info(repo_id, revision, token)
        else:
            from huggingface_hub import HfApi

            info = HfApi(token=token or None).model_info(repo_id, revision=revision, files_metadata=True)
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        name = type(exc).__name__
        if status in (401, 403) or name in {"GatedRepoError", "LocalTokenNotFoundError"} or "gated" in name.lower():
            result.needs_token = True
            result.message = "This Hugging Face model needs a token before Adept UI can download it."
            result.detail = "Add a Hugging Face token in LoRA Manager. The token stays on this computer."
            return result
        result.message = "Adept UI could not read that Hugging Face model."
        result.detail = name
        return result
    card = getattr(info, "card_data", None) or {}
    if not isinstance(card, dict):
        card = getattr(card, "to_dict", lambda: {})() or {}
    base = str(card.get("base_model") or "")
    if isinstance(card.get("base_model"), list) and card.get("base_model"):
        base = str(card["base_model"][0])
    result.base_model = base
    result.family = family_from_base_model(base)
    result.license = str(card.get("license") or "")
    result.author = repo_id.split("/")[0]
    result.source_version = str(getattr(info, "sha", None) or parsed.get("revision") or "")
    result.files = _hf_siblings(info)
    result.selected = _select_file(result.files, parsed.get("file_path") or "")
    if not result.files:
        result.message = "That Hugging Face model does not include a .safetensors LoRA file."
        return result
    if result.selected is None:
        result.message = "Choose which LoRA file to install."
    else:
        result.display_name = Path(result.selected.filename).stem
        result.message = "LoRA found."
    return result


def _civitai_headers() -> dict[str, str]:
    headers = {"User-Agent": "AdeptUI/1.0", "Accept": "application/json"}
    token = civitai_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _http_json(url: str, http_get: Callable | None) -> tuple[int, dict]:
    if http_get is not None:
        status, payload = http_get(url)
        return int(status), payload if isinstance(payload, dict) else {}
    import httpx

    response = httpx.get(url, headers=_civitai_headers(), timeout=30.0, follow_redirects=True)
    try:
        payload = response.json()
    except Exception:
        payload = {}
    return response.status_code, payload if isinstance(payload, dict) else {}


def _civitai_files(version: dict) -> list[LoraSourceFile]:
    files: list[LoraSourceFile] = []
    version_id = str(version.get("id") or "")
    for item in version.get("files") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if not name.lower().endswith(".safetensors"):
            continue
        meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        format_name = str(meta.get("format") or item.get("type") or "")
        if format_name and "pickle" in format_name.lower():
            continue
        hashes = item.get("hashes") if isinstance(item.get("hashes"), dict) else {}
        size_kb = item.get("sizeKB")
        try:
            size = int(float(size_kb) * 1024) if size_kb is not None else None
        except (TypeError, ValueError):
            size = None
        files.append(
            LoraSourceFile(
                filename=name,
                size_bytes=size,
                sha256=str(hashes.get("SHA256") or hashes.get("sha256") or ""),
                download_url=f"https://civitai.com/api/download/models/{version_id}",
            )
        )
    return files


def _resolve_civitai(parsed: dict[str, str], *, http_get: Callable | None = None) -> LoraSourceResolution:
    result = LoraSourceResolution(
        provider="civitai",
        source_url=parsed["source_url"],
        token_provider="civitai",
    )
    model_id = parsed.get("model_id") or ""
    version_id = parsed.get("version_id") or ""
    if model_id:
        status, payload = _http_json(f"https://civitai.com/api/v1/models/{model_id}", http_get)
    else:
        status, payload = _http_json(f"https://civitai.com/api/v1/model-versions/{version_id}", http_get)
        if status == 200:
            model_id = str(payload.get("modelId") or "")
            payload = {"name": payload.get("model", {}).get("name") if isinstance(payload.get("model"), dict) else "", "type": "LORA", "modelVersions": [payload], "creator": {}}
    if status in (401, 403):
        result.needs_token = True
        result.message = "This Civitai download needs a Civitai API token."
        result.detail = "Add the token in LoRA Manager. Adept UI stores it on this computer and does not put it in the LoRA record."
        return result
    if status != 200 or not payload:
        result.message = "Adept UI could not read that Civitai model."
        result.detail = f"HTTP {status}" if status else "no response"
        return result
    model_type = str(payload.get("type") or "").upper()
    versions = payload.get("modelVersions") if isinstance(payload.get("modelVersions"), list) else []
    version = None
    if version_id:
        version = next((item for item in versions if str(item.get("id")) == str(version_id)), None)
    if version is None and versions:
        version = versions[0]
    if not isinstance(version, dict):
        result.message = "That Civitai page does not list a downloadable version."
        return result
    if model_type and model_type not in {"LORA", "LYCORIS", ""}:
        result.message = "That Civitai page is not a LoRA. Adept UI will not install it."
        result.detail = model_type
        return result
    result.display_name = str(payload.get("name") or version.get("name") or "LoRA")
    result.source_model_id = str(payload.get("id") or model_id or version.get("modelId") or "")
    result.source_version = str(version.get("id") or "")
    result.base_model = str(version.get("baseModel") or "")
    result.family = family_from_base_model(result.base_model)
    creator = payload.get("creator") if isinstance(payload.get("creator"), dict) else {}
    result.author = str(creator.get("username") or "")
    words = version.get("trainedWords") if isinstance(version.get("trainedWords"), list) else []
    result.trigger_words = [str(word).strip() for word in words if str(word).strip()]
    result.files = _civitai_files(version)
    result.selected = _select_file(result.files, "")
    if not result.files:
        result.message = "That Civitai version does not include a .safetensors LoRA file."
        return result
    result.message = "LoRA found." if result.selected else "Choose which LoRA file to install."
    return result


def resolve_lora_source(
    url: str,
    *,
    http_get: Callable | None = None,
    hf_info: Callable | None = None,
) -> LoraSourceResolution:
    parsed = parse_lora_url(url)
    if parsed["provider"] == "huggingface":
        return _resolve_huggingface(parsed, hf_info=hf_info)
    return _resolve_civitai(parsed, http_get=http_get)


def download_source_file(selected: LoraSourceFile, dest: Path, *, provider: str) -> None:
    """Download one resolved artifact. The destination is replaced only after success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".partial")
    if partial.exists():
        partial.unlink()
    try:
        if provider == "huggingface":
            from huggingface_hub import hf_hub_download

            downloaded = hf_hub_download(
                repo_id=selected.repo_id,
                filename=selected.filename,
                revision=selected.revision or None,
                token=huggingface_token() or None,
                local_dir=str(dest.parent),
            )
            downloaded_path = Path(downloaded)
            if downloaded_path.resolve() != dest.resolve():
                downloaded_path.replace(dest)
            return
        if not selected.download_url:
            raise ValueError("That LoRA does not have a download link.")
        import httpx

        with httpx.stream("GET", selected.download_url, headers=_civitai_headers(), timeout=120.0, follow_redirects=True) as response:
            if response.status_code in (401, 403):
                raise ValueError("This Civitai download needs a Civitai API token.")
            if response.status_code != 200:
                raise ValueError("The LoRA download did not finish.")
            content_type = (response.headers.get("content-type") or "").lower()
            if "text/html" in content_type:
                raise ValueError("The download page did not return a LoRA file. A token may be required.")
            from .metadata import MAX_LORA_BYTES

            size = 0
            with open(partial, "wb") as handle:
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_LORA_BYTES:
                        raise ValueError("That file is larger than Adept UI will install as a LoRA.")
                    handle.write(chunk)
        partial.replace(dest)
    except ValueError:
        if partial.exists():
            partial.unlink(missing_ok=True)
        raise
    except Exception:
        if partial.exists():
            partial.unlink(missing_ok=True)
        raise ValueError("The LoRA download did not finish.")
    finally:
        if partial.exists() and dest.exists():
            partial.unlink(missing_ok=True)
