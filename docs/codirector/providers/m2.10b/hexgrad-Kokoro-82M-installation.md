# M2.10b Installation Report — `hexgrad/Kokoro-82M`

**Status:** STUB — not installed in this documentation pass.
**Branch:** `phase2/codirector-m2-9-production-suite`
**Start SHA:** `c805d0c5b0b9a535b386ea38d09198460996d828`
**Date:** 2026-07-26
**Provider Manifest sha256 (must remain unchanged):** `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc`
**Gate 6 product lock sha256:** `7f26170dafccae376ec6227211efd3450338b4c22cb95f5a4fc47c43d7a3419b` (install/execute/weight **false**)
**Phase 0:** `READY FOR M2.10b SANDBOX` — `docs/codirector/m2.10b-phase0-preflight-checkpoint.md`

## Identity

| Field | Value |
| --- | --- |
| Registry ID | `m2101-dialogue-001` |
| Source key | `hexgrad/Kokoro-82M` |
| Capability | `audio.dialogue.generate` |
| License (discovery) | `apache-2.0` |
| Repository / model URL | `https://huggingface.co/hexgrad/Kokoro-82M` |
| Gate 6 install/execute/weight | **false** (`7f26170dafccae376ec6227211efd3450338b4c22cb95f5a4fc47c43d7a3419b`) |
| Execution-lock scope | Authorized as one of nine audio candidates (M2.10b prompt provenance); lock file fill **pending** |
| Production authorized | **false** |
| Sandbox only | **true** |

## Primary real-generation target

This candidate is the **primary real-generation target** for M2.10b dialogue acceptance. At least one real local generation path is required for operational acceptance; prefer completing Kokoro before treating dialogue as proven.

## Pinning (pending)

| Field | Value |
| --- | --- |
| Git commit / revision | TBD |
| Model revision | TBD |
| Downloaded file hashes | TBD |
| Environment identifier | TBD |
| Sandbox path | TBD (planned under `data/m210b-sandbox/`) |

## Dependency / security notes

| Item | Value |
| --- | --- |
| Dependencies recorded | PENDING |
| `trust_remote_code` / custom CUDA / Triton / xFormers / FlashAttention / ffmpeg | PENDING |
| Unsafe binary rejection | PENDING |
| License change at install | PENDING — do not auto-accept |

## Runtime

| Check | Result |
| --- | --- |
| Isolated install | PENDING |
| Health check | PENDING |
| Real generation | PENDING |
| VRAM / latency | PENDING |

## Notes

Primary real-generation target for M2.10b dialogue acceptance path.

## Install run (2026-07-26T21:41:16+00:00)

Sandbox root: `C:/AdeptFilmWorks/AIVideoStudio/data/m210b-sandbox/providers/m2101-dialogue-001`
Creating venv…
pip install kokoro soundfile numpy huggingface_hub
pip exit=1
```
whl (161 kB)
   ---------------------------------------- 161.4/161.4 kB 10.1 MB/s eta 0:00:00

Downloading cloudpathlib-0.24.0-py3-none-any.whl (63 kB)
   ---------------------------------------- 63.2/63.2 kB ? eta 0:00:00

Downloading csvw-4.1.0-py2.py3-none-any.whl (69 kB)
   ---------------------------------------- 69.5/69.5 kB ? eta 0:00:00

Downloading markdown_it_py-4.2.0-py3-none-any.whl (91 kB)
   ---------------------------------------- 91.7/91.7 kB ? eta 0:00:00

Downloading pygments-2.20.0-py3-none-any.whl (1.2 MB)
   ---------------------------------------- 1.2/1.2 MB 26.0 MB/s eta 0:00:00

Downloading smart_open-8.0.1-py3-none-any.whl (73 kB)
   ---------------------------------------- 73.5/73.5 kB 4.2 MB/s eta 0:00:00

Using cached typing_inspection-0.4.2-py3-none-any.whl (14 kB)
Downloading urllib3-2.7.0-py3-none-any.whl (131 kB)
   ---------------------------------------- 131.1/131.1 kB ? eta 0:00:00

Downloading mdurl-0.1.2-py3-none-any.whl (10.0 kB)
Downloading rfc3986-1.5.0-py2.py3-none-any.whl (31 kB)
Downloading uritemplate-4.2.0-py3-none-any.whl (11 kB)
Downloading babel-2.18.0-py3-none-any.whl (10.2 MB)
   ---------------------------------------- 10.2/10.2 MB 21.0 MB/s eta 0:00:00

Downloading isodate-0.7.2-py3-none-any.whl (22 kB)
Downloading jsonschema-4.26.0-py3-none-any.whl (90 kB)
   ---------------------------------------- 90.6/90.6 kB ? eta 0:00:00

Downloading language_tags-1.3.1-py3-none-any.whl (216 kB)
   ---------------------------------------- 216.7/216.7 kB 12.9 MB/s eta 0:00:00

Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
Downloading rdflib-7.6.0-py3-none-any.whl (615 kB)
   ---------------------------------------- 615.4/615.4 kB 19.5 MB/s eta 0:00:00

Downloading termcolor-3.3.0-py3-none-any.whl (7.7 kB)
Downloading wrapt-2.2.2-cp311-cp311-win_amd64.whl (80 kB)
   ---------------------------------------- 80.4/80.4 kB ? eta 0:00:00

Downloading jsonschema_specifications-2025.9.1-py3-none-any.whl (18 kB)
Using cached pyparsing-3.3.2-py3-none-any.whl (122 kB)
Downloading referencing-0.37.0-py3-none-any.whl (26 kB)
Downloading rpds_py-2026.6.3-cp311-cp311-win_amd64.whl (223 kB)
   ---------------------------------------- 223.2/223.2 kB ? eta 0:00:00

Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
Building wheels for collected packages: docopt
  Building wheel for docopt (pyproject.toml): started
  Building wheel for docopt (pyproject.toml): finished with status 'done'
  Created wheel for docopt: filename=docopt-0.6.2-py2.py3-none-any.whl size=13857 sha256=5e55cefef7466c6e7a3d03f2c0f04377b3bf95a06389a823f5788c193492a706
  Stored in directory: c:\users\bradj\appdata\local\temp\cursor-sandbox-cache\15c825fa9e763fd8155cd5a6757a56c4\pip\wheels\1a\b0\8c\4b75c4116c31f83c8f9f047231251e13cc74481cca4a78a9ce
Successfully built docopt
Installing collected packages: rfc3986, mpmath, docopt, addict, wrapt, win32-setctime, urllib3, uritemplate, typing-extensions, termcolor, sympy, spacy-loggers, spacy-legacy, six, shellingham, safetensors, rpds-py, regex, pyyaml, pyparsing, pygments, pycparser, pip, packaging, numpy, num2words, networkx, murmurhash, mdurl, MarkupSafe, language-tags, joblib, isodate, idna, hf-xet, h11, fsspec, filelock, espeakng-loader, dlinfo, cymem, confection, colorama, cloudpathlib, charset_normalizer, certifi, catalogue, babel, attrs, annotated-types, annotated-doc, wasabi, typing-inspection, tqdm, srsly, smart-open, requests, referencing, rdflib, python-dateutil, pydantic-core, preshed, misaki, markdown-it-py, loguru, jinja2, httpcore, curated-tokenizers, click, cffi, blis, anyio, torch, soundfile, rich, pydantic, jsonschema-specifications, httpx, typer, thinc, jsonschema, huggingface_hub, curated-transformers, weasel, tokenizers, spacy-curated-transformers, csvw, transformers, spacy, segments, phonemizer-fork, kokoro
  Attempting uninstall: pip
    Found existing installation: pip 24.0
    Uninstalling pip-24.0:
      Successfully uninstalled pip-24.0

```
```
ERROR: Could not install packages due to an OSError: [WinError 206] The filename or extension is too long: 'C:\\AdeptFilmWorks\\AIVideoStudio\\data\\m210b-sandbox\\providers\\m2101-dialogue-001\\venv\\Lib\\site-packages\\torch-2.13.0.dist-info\\licenses\\third_party\\kineto\\libkineto\\third_party\\dynolog\\third_party\\prometheus-cpp\\3rdparty\\civetweb\\examples\\rest\\cJSON'


```
**Error:** `pip install failed`
```
Traceback (most recent call last):
  File "C:\AdeptFilmWorks\AIVideoStudio\scripts\_install_m210b_kokoro.py", line 113, in main
    raise RuntimeError("pip install failed")
RuntimeError: pip install failed

```

## Install run (2026-07-26T21:43:19+00:00)

Sandbox root: `C:/AdeptFilmWorks/AIVideoStudio/data/m210b-sandbox/providers/m2101-dialogue-001`
Short venv path (MAX_PATH): `C:/AdeptFilmWorks/AIVideoStudio/data/m210b-kvenv`
Creating/reusing short venv + junction at providers/.../venv
venv python: `C:\AdeptFilmWorks\AIVideoStudio\data\m210b-kvenv\Scripts\python.exe`
pip install kokoro soundfile numpy huggingface_hub
pip exit=0
```
 cached cloudpathlib-0.24.0-py3-none-any.whl (63 kB)
Using cached csvw-4.1.0-py2.py3-none-any.whl (69 kB)
Using cached markdown_it_py-4.2.0-py3-none-any.whl (91 kB)
Using cached pygments-2.20.0-py3-none-any.whl (1.2 MB)
Using cached smart_open-8.0.1-py3-none-any.whl (73 kB)
Using cached typing_inspection-0.4.2-py3-none-any.whl (14 kB)
Using cached urllib3-2.7.0-py3-none-any.whl (131 kB)
Using cached mdurl-0.1.2-py3-none-any.whl (10.0 kB)
Using cached rfc3986-1.5.0-py2.py3-none-any.whl (31 kB)
Using cached uritemplate-4.2.0-py3-none-any.whl (11 kB)
Using cached babel-2.18.0-py3-none-any.whl (10.2 MB)
Using cached isodate-0.7.2-py3-none-any.whl (22 kB)
Using cached jsonschema-4.26.0-py3-none-any.whl (90 kB)
Using cached language_tags-1.3.1-py3-none-any.whl (216 kB)
Using cached python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
Using cached rdflib-7.6.0-py3-none-any.whl (615 kB)
Using cached termcolor-3.3.0-py3-none-any.whl (7.7 kB)
Using cached wrapt-2.2.2-cp311-cp311-win_amd64.whl (80 kB)
Using cached jsonschema_specifications-2025.9.1-py3-none-any.whl (18 kB)
Using cached pyparsing-3.3.2-py3-none-any.whl (122 kB)
Using cached referencing-0.37.0-py3-none-any.whl (26 kB)
Using cached rpds_py-2026.6.3-cp311-cp311-win_amd64.whl (223 kB)
Using cached six-1.17.0-py2.py3-none-any.whl (11 kB)
Installing collected packages: rfc3986, mpmath, docopt, addict, wrapt, win32-setctime, urllib3, uritemplate, typing-extensions, termcolor, sympy, spacy-loggers, spacy-legacy, six, shellingham, safetensors, rpds-py, regex, pyyaml, pyparsing, pygments, pycparser, pip, packaging, numpy, num2words, networkx, murmurhash, mdurl, MarkupSafe, language-tags, joblib, isodate, idna, hf-xet, h11, fsspec, filelock, espeakng-loader, dlinfo, cymem, confection, colorama, cloudpathlib, charset_normalizer, certifi, catalogue, babel, attrs, annotated-types, annotated-doc, wasabi, typing-inspection, tqdm, srsly, smart-open, requests, referencing, rdflib, python-dateutil, pydantic-core, preshed, misaki, markdown-it-py, loguru, jinja2, httpcore, curated-tokenizers, click, cffi, blis, anyio, torch, soundfile, rich, pydantic, jsonschema-specifications, httpx, typer, thinc, jsonschema, huggingface_hub, curated-transformers, weasel, tokenizers, spacy-curated-transformers, csvw, transformers, spacy, segments, phonemizer-fork, kokoro
  Attempting uninstall: pip
    Found existing installation: pip 24.0
    Uninstalling pip-24.0:
      Successfully uninstalled pip-24.0
Successfully installed MarkupSafe-3.0.3 addict-2.4.0 annotated-doc-0.0.4 annotated-types-0.8.0 anyio-4.14.2 attrs-26.1.0 babel-2.18.0 blis-1.3.3 catalogue-2.0.10 certifi-2026.7.22 cffi-2.1.0 charset_normalizer-3.4.9 click-8.4.2 cloudpathlib-0.24.0 colorama-0.4.6 confection-1.3.3 csvw-4.1.0 curated-tokenizers-0.0.9 curated-transformers-0.1.1 cymem-2.0.13 dlinfo-2.0.0 docopt-0.6.2 espeakng-loader-0.2.4 filelock-3.32.0 fsspec-2026.6.0 h11-0.16.0 hf-xet-1.5.2 httpcore-1.0.9 httpx-0.28.1 huggingface_hub-1.24.0 idna-3.18 isodate-0.7.2 jinja2-3.1.6 joblib-1.5.3 jsonschema-4.26.0 jsonschema-specifications-2025.9.1 kokoro-0.9.4 language-tags-1.3.1 loguru-0.7.3 markdown-it-py-4.2.0 mdurl-0.1.2 misaki-0.9.4 mpmath-1.3.0 murmurhash-1.0.15 networkx-3.6.1 num2words-0.5.14 numpy-2.4.6 packaging-26.2 phonemizer-fork-3.3.2 pip-26.1.2 preshed-3.0.13 pycparser-3.0 pydantic-2.13.4 pydantic-core-2.46.4 pygments-2.20.0 pyparsing-3.3.2 python-dateutil-2.9.0.post0 pyyaml-6.0.3 rdflib-7.6.0 referencing-0.37.0 regex-2026.7.19 requests-2.34.2 rfc3986-1.5.0 rich-15.0.0 rpds-py-2026.6.3 safetensors-0.8.0 segments-2.4.0 shellingham-1.5.4 six-1.17.0 smart-open-8.0.1 soundfile-0.14.0 spacy-3.8.14 spacy-curated-transformers-0.3.1 spacy-legacy-3.0.12 spacy-loggers-1.0.5 srsly-2.5.3 sympy-1.14.0 termcolor-3.3.0 thinc-8.3.13 tokenizers-0.22.2 torch-2.13.0 tqdm-4.69.1 transformers-5.14.1 typer-0.27.0 typing-extensions-4.16.0 typing-inspection-0.4.2 uritemplate-4.2.0 urllib3-2.7.0 wasabi-1.1.3 weasel-1.0.0 win32-setctime-1.2.0 wrapt-2.2.2

```
snapshot_download hexgrad/Kokoro-82M -> models/
download exit=0
```
C:\AdeptFilmWorks\AIVideoStudio\data\m210b-sandbox\providers\m2101-dialogue-001\models

```
Wrote models/READY
Generating smoke WAV via KPipeline…
generate exit=1
```
Traceback (most recent call last):
  File "<string>", line 9, in <module>
  File "C:\AdeptFilmWorks\AIVideoStudio\data\m210b-kvenv\Lib\site-packages\kokoro\pipeline.py", line 99, in __init__
    self.model = KModel(repo_id=repo_id).to(device).eval()
                 ^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\AdeptFilmWorks\AIVideoStudio\data\m210b-kvenv\Lib\site-packages\kokoro\model.py", line 46, in __init__
    config = hf_hub_download(repo_id=repo_id, filename='config.json')
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\AdeptFilmWorks\AIVideoStudio\data\m210b-kvenv\Lib\site-packages\huggingface_hub\utils\_validators.py", line 84, in _inner_fn
    validate_repo_id(arg_value)
  File "C:\AdeptFilmWorks\AIVideoStudio\data\m210b-kvenv\Lib\site-packages\huggingface_hub\utils\_validators.py", line 138, in validate_repo_id
    raise HFValidationError(
huggingface_hub.errors.HFValidationError: Repo id must use alphanumeric chars, '-', '_' or '.'. The name cannot start or end with '-' or '.' and the maximum length is 96: 'C:\AdeptFilmWorks\AIVideoStudio\data\m210b-sandbox\providers\m2101-dialogue-001\models'.

```
**Error:** `KPipeline smoke generation failed`
```
Traceback (most recent call last):
  File "C:\AdeptFilmWorks\AIVideoStudio\scripts\_install_m210b_kokoro.py", line 212, in main
    raise RuntimeError("KPipeline smoke generation failed")
RuntimeError: KPipeline smoke generation failed

```

## Install run (2026-07-26T21:44:22+00:00)

Sandbox root: `C:/AdeptFilmWorks/AIVideoStudio/data/m210b-sandbox/providers/m2101-dialogue-001`
Short venv path (MAX_PATH): `C:/AdeptFilmWorks/AIVideoStudio/data/m210b-kvenv`
Creating/reusing short venv + junction at providers/.../venv
venv python: `C:\AdeptFilmWorks\AIVideoStudio\data\m210b-kvenv\Scripts\python.exe`
pip install kokoro soundfile numpy huggingface_hub
pip exit=0
```
ages (from spacy->misaki[en]>=0.9.4->kokoro) (1.0.0)
Requirement already satisfied: confection<2.0.0,>=1.3.2 in .\Lib\site-packages (from spacy->misaki[en]>=0.9.4->kokoro) (1.3.3)
Requirement already satisfied: typer<1.0.0,>=0.3.0 in .\Lib\site-packages (from spacy->misaki[en]>=0.9.4->kokoro) (0.27.0)
Requirement already satisfied: requests<3.0.0,>=2.13.0 in .\Lib\site-packages (from spacy->misaki[en]>=0.9.4->kokoro) (2.34.2)
Requirement already satisfied: pydantic<3.0.0,>=2.0.0 in .\Lib\site-packages (from spacy->misaki[en]>=0.9.4->kokoro) (2.13.4)
Requirement already satisfied: jinja2 in .\Lib\site-packages (from spacy->misaki[en]>=0.9.4->kokoro) (3.1.6)
Requirement already satisfied: setuptools in .\Lib\site-packages (from spacy->misaki[en]>=0.9.4->kokoro) (79.0.1)
Requirement already satisfied: annotated-types>=0.6.0 in .\Lib\site-packages (from pydantic<3.0.0,>=2.0.0->spacy->misaki[en]>=0.9.4->kokoro) (0.8.0)
Requirement already satisfied: pydantic-core==2.46.4 in .\Lib\site-packages (from pydantic<3.0.0,>=2.0.0->spacy->misaki[en]>=0.9.4->kokoro) (2.46.4)
Requirement already satisfied: typing-inspection>=0.4.2 in .\Lib\site-packages (from pydantic<3.0.0,>=2.0.0->spacy->misaki[en]>=0.9.4->kokoro) (0.4.2)
Requirement already satisfied: charset_normalizer<4,>=2 in .\Lib\site-packages (from requests<3.0.0,>=2.13.0->spacy->misaki[en]>=0.9.4->kokoro) (3.4.9)
Requirement already satisfied: urllib3<3,>=1.26 in .\Lib\site-packages (from requests<3.0.0,>=2.13.0->spacy->misaki[en]>=0.9.4->kokoro) (2.7.0)
Requirement already satisfied: blis<1.4.0,>=1.3.0 in .\Lib\site-packages (from thinc<8.4.0,>=8.3.12->spacy->misaki[en]>=0.9.4->kokoro) (1.3.3)
Requirement already satisfied: shellingham>=1.3.0 in .\Lib\site-packages (from typer<1.0.0,>=0.3.0->spacy->misaki[en]>=0.9.4->kokoro) (1.5.4)
Requirement already satisfied: rich>=13.8.0 in .\Lib\site-packages (from typer<1.0.0,>=0.3.0->spacy->misaki[en]>=0.9.4->kokoro) (15.0.0)
Requirement already satisfied: annotated-doc>=0.0.2 in .\Lib\site-packages (from typer<1.0.0,>=0.3.0->spacy->misaki[en]>=0.9.4->kokoro) (0.0.4)
Requirement already satisfied: cloudpathlib>=0.7.0 in .\Lib\site-packages (from weasel<2.0.0,>=1.0.0->spacy->misaki[en]>=0.9.4->kokoro) (0.24.0)
Requirement already satisfied: smart-open>=5.2.1 in .\Lib\site-packages (from weasel<2.0.0,>=1.0.0->spacy->misaki[en]>=0.9.4->kokoro) (8.0.1)
Requirement already satisfied: markdown-it-py>=2.2.0 in .\Lib\site-packages (from rich>=13.8.0->typer<1.0.0,>=0.3.0->spacy->misaki[en]>=0.9.4->kokoro) (4.2.0)
Requirement already satisfied: pygments<3.0.0,>=2.13.0 in .\Lib\site-packages (from rich>=13.8.0->typer<1.0.0,>=0.3.0->spacy->misaki[en]>=0.9.4->kokoro) (2.20.0)
Requirement already satisfied: mdurl~=0.1 in .\Lib\site-packages (from markdown-it-py>=2.2.0->rich>=13.8.0->typer<1.0.0,>=0.3.0->spacy->misaki[en]>=0.9.4->kokoro) (0.1.2)
Requirement already satisfied: wrapt in .\Lib\site-packages (from smart-open>=5.2.1->weasel<2.0.0,>=1.0.0->spacy->misaki[en]>=0.9.4->kokoro) (2.2.2)
Requirement already satisfied: MarkupSafe>=2.0 in .\Lib\site-packages (from jinja2->spacy->misaki[en]>=0.9.4->kokoro) (3.0.3)
Requirement already satisfied: curated-transformers<0.2.0,>=0.1.0 in .\Lib\site-packages (from spacy-curated-transformers->misaki[en]>=0.9.4->kokoro) (0.1.1)
Requirement already satisfied: curated-tokenizers<0.1.0,>=0.0.9 in .\Lib\site-packages (from spacy-curated-transformers->misaki[en]>=0.9.4->kokoro) (0.0.9)
Requirement already satisfied: sympy>=1.13.3 in .\Lib\site-packages (from torch->kokoro) (1.14.0)
Requirement already satisfied: networkx>=2.5.1 in .\Lib\site-packages (from torch->kokoro) (3.6.1)
Requirement already satisfied: mpmath<1.4,>=1.1.0 in .\Lib\site-packages (from sympy>=1.13.3->torch->kokoro) (1.3.0)
Requirement already satisfied: tokenizers<=0.23.0,>=0.22.0 in .\Lib\site-packages (from transformers->kokoro) (0.22.2)
Requirement already satisfied: safetensors>=0.8.0 in .\Lib\site-packages (from transformers->kokoro) (0.8.0)

```
snapshot_download hexgrad/Kokoro-82M -> models/
download exit=0
```
C:\AdeptFilmWorks\AIVideoStudio\data\m210b-sandbox\providers\m2101-dialogue-001\models

```
Wrote models/READY
Generating smoke WAV via KPipeline…
generate exit=0
```
Collecting en-core-web-sm==3.8.0
  Downloading en_core_web_sm-3.8.0-py3-none-any.whl (12.8 MB)
     ---------------------------------------- 12.8/12.8 MB 28.7 MB/s  0:00:00

Installing collected packages: en-core-web-sm
Successfully installed en-core-web-sm-3.8.0
[38;5;2m[+] Download and installation successful[0m
You can now load the package via spacy.load('en_core_web_sm')
C:\AdeptFilmWorks\AIVideoStudio\data\m210b-sandbox\providers\m2101-dialogue-001\output\m210b-kokoro-smoke.wav 159644 device cpu

```
Smoke WAV: `C:/AdeptFilmWorks/AIVideoStudio/data/m210b-sandbox/providers/m2101-dialogue-001/output/m210b-kokoro-smoke.wav` (159644 bytes)
Wrote install-manifest.json installed=true

---

INSTALLATION PASSED
