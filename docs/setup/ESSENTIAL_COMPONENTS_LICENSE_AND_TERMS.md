# Adept UI Essential Components — License and Terms

**Notice version:** 2026.08.1  
**Effective date:** 2026-08-26  
**Document id:** `essential-components-license-and-terms`  
**Canonical path:** `docs/setup/ESSENTIAL_COMPONENTS_LICENSE_AND_TERMS.md`

This is the single consolidated Essential Components notice for Adept UI. Accepting it records that you have read this version. It does **not** replace tool-specific licenses you may still accept when linking Wonder3D, FLUX, or other peripheral tools.

Adept UI serves this notice through Setup. If this document cannot be loaded, Setup must show that it is unavailable and must **not** treat the notice as accepted.

---

## 1. What you are agreeing to

Adept UI includes **Essential Components** that core creator paths depend on. Essential means architectural role — not “already downloaded” and not “Ready.”

Until you agree to the **current** version of this notice:

- Adept UI will not install or activate Essential Components.
- Declining or leaving Setup leaves those components ineligible.

A later material change to this notice gets a new version. You will be asked to agree again. Prior agreement does not carry forward.

---

## 2. Independent facts (read these as separate)

For each Essential, Adept UI tracks these independently:

| Fact | Meaning |
|---|---|
| Agreement Accepted | You agreed to this notice version |
| Source Installed | Official source is present on disk |
| Runtime Ready | Isolated runtime can start |
| Commercial Model Access | Official host has granted the commercial model |
| Model Ready | Required weights are present and verified |
| GPU Ready | The intended GPU is available for that runtime |
| Production Certified | The product path has passed its certification gate |

A folder on disk is not agreement. A git clone is not Ready. Missing commercial access does not make an Essential “peripheral.”

---

## 3. Essential registry (this version)

### 3.1 MoGe-2 Geometry Reconstruction

| Field | Value |
|---|---|
| Component id | `moge2_geometry` |
| Display name | MoGe-2 Geometry Reconstruction |
| Role | Single-image geometry for Spatial Map / Atlas (Express, and Standard when only one observed image exists) |
| Product class | ESSENTIAL |
| Publisher | Microsoft Research / MoGe authors |
| Code source | GitHub `microsoft/MoGe` first |
| Weights source | Official Hugging Face card only when install is authorized |
| Code license | MIT for MoGe code (DINOv2 subtree Apache-2.0) |
| Weights license | **Unconfirmed** — Adept does **not** treat MoGe weights as MIT or Apache-2.0 |
| License status | `OWNER_PERMITTED_LICENSE_PENDING_CLARIFICATION` |
| Owner policy | `PERMITTED` |

Adept permits MoGe-2 under owner policy so Spatial Map Express can be built. Weight terms are pending official clarification from Microsoft / the MoGe publishers. This record will be updated if the publisher clarifies the weight license. Until then, Adept will not write a false SPDX for the weights.

### 3.2 VGGT-1B Commercial Geometry Reconstruction

| Field | Value |
|---|---|
| Component id | `vggt_1b_commercial` |
| Display name | VGGT-1B Commercial Geometry Reconstruction |
| Role | Standard Spatial Map multi-view geometry reconstruction |
| Product class | ESSENTIAL |
| Publisher | Meta |
| Code source | Official GitHub `facebookresearch/vggt` |
| Model source | `facebook/VGGT-1B-Commercial` **only** |
| License status | `REQUIRES_EXTERNAL_ACCEPTANCE` and `MODEL_ACCESS_GATED` |
| Owner policy | `PERMITTED` |

VGGT is Essential because Standard Spatial Map depends on it. Gated commercial-weight access does **not** make it peripheral, and it does **not** become Ready because the GitHub repository was cloned.

Adept will not use `facebook/VGGT-1B` (non-commercial). Commercial model access is a separate fact from this Adept notice. You may still need to accept Meta / Hugging Face terms on the official model card before weights can be downloaded.

**Independence:** If VGGT commercial weights are not available, Adept must still allow install and use of unrelated Essentials and MoGe-2 Express.

---

## 4. Upstream VGGT license and Acceptable Use Policy

The following is the official VGGT License and Acceptable Use Policy as published with the VGGT research materials (v1, last updated July 29, 2025). Adept includes it here so this Essential notice identifies upstream terms accurately. Commercial model access for `facebook/VGGT-1B-Commercial` remains separately gated.

```
VGGT License

v1 Last Updated: July 29, 2025

“Acceptable Use Policy” means the Acceptable Use Policy, applicable to Research Materials, that is incorporated into this Agreement.

“Agreement” means the terms and conditions for use, reproduction, distribution and modification of the Research Materials set forth herein.

“Documentation” means the specifications, manuals and documentation accompanying
Research Materials distributed by Meta.

“Licensee” or “you” means you, or your employer or any other person or entity (if you are entering into this Agreement on such person or entity’s behalf), of the age required under applicable laws, rules or regulations to provide legal consent and that has legal authority to bind your employer or such other person or entity if you are entering in this Agreement on their behalf.

“Meta” or “we” means Meta Platforms Ireland Limited (if you are located in or, if you are an entity, your principal place of business is in the EEA or Switzerland) and Meta Platforms, Inc. (if you are located outside of the EEA or Switzerland).
“Research Materials” means, collectively, Documentation and the models, software and algorithms, including machine-learning model code, trained model weights, inference-enabling code, training-enabling code, fine-tuning enabling code, demonstration materials and other elements of the foregoing distributed by Meta and made available under this Agreement.

By clicking “I Accept” below or by using or distributing any portion or element of the Research Materials, you agree to be bound by this Agreement.

1. License Rights and Redistribution.

a. Grant of Rights. You are granted a non-exclusive, worldwide, non-transferable and royalty-free limited license under Meta’s intellectual property or other rights owned by Meta embodied in the Research Materials to use, reproduce, distribute, copy, create derivative works of, and make modifications to the Research Materials.

b. Redistribution and Use.

i. Distribution of Research Materials, and any derivative works thereof, are subject to the terms of this Agreement. If you distribute or make the Research Materials, or any derivative works thereof, available to a third party, you may only do so under the terms of this Agreement. You shall also provide a copy of this Agreement to such third party.

ii. If you submit for publication the results of research you perform on, using, or otherwise in connection with Research Materials, you must acknowledge the use of Research Materials in your publication.

iii. Your use of the Research Materials must comply with applicable laws and regulations (including Trade Control Laws) and adhere to the Acceptable Use Policy, which is hereby incorporated by reference into this Agreement.

2. User Support. Your use of the Research Materials is done at your own discretion; Meta does not process any information nor provide any service in relation to such use. Meta is under no obligation to provide any support services for the Research Materials. Any support provided is “as is”, “with all faults”, and without warranty of any kind.

3. Disclaimer of Warranty. UNLESS REQUIRED BY APPLICABLE LAW, THE RESEARCH MATERIALS AND ANY OUTPUT AND RESULTS THEREFROM ARE PROVIDED ON AN “AS IS” BASIS, WITHOUT WARRANTIES OF ANY KIND, AND META DISCLAIMS ALL WARRANTIES OF ANY KIND, BOTH EXPRESS AND IMPLIED, INCLUDING, WITHOUT LIMITATION, ANY WARRANTIES OF TITLE, NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE. YOU ARE SOLELY RESPONSIBLE FOR DETERMINING THE APPROPRIATENESS OF USING OR REDISTRIBUTING THE RESEARCH MATERIALS AND ASSUME ANY RISKS ASSOCIATED WITH YOUR USE OF THE RESEARCH MATERIALS AND ANY OUTPUT AND RESULTS.

4. Limitation of Liability. IN NO EVENT WILL META OR ITS AFFILIATES BE LIABLE UNDER ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, TORT, NEGLIGENCE, PRODUCTS LIABILITY, OR OTHERWISE, ARISING OUT OF THIS AGREEMENT, FOR ANY LOST PROFITS OR ANY DIRECT OR INDIRECT, SPECIAL, CONSEQUENTIAL, INCIDENTAL, EXEMPLARY OR PUNITIVE DAMAGES, EVEN IF META OR ITS AFFILIATES HAVE BEEN ADVISED OF THE POSSIBILITY OF ANY OF THE FOREGOING.

5. Intellectual Property.

a. Subject to Meta’s ownership of Research Materials and derivatives made by or for Meta, with respect to any derivative works and modifications of the Research Materials that are made by you, as between you and Meta, you are and will be the owner of such derivative works and modifications.

b. If you institute litigation or other proceedings against Meta or any entity (including a cross-claim or counterclaim in a lawsuit) alleging that the Research Materials, outputs or results, or any portion of any of the foregoing, constitutes infringement of intellectual property or other rights owned or licensable by you, then any licenses granted to you under this Agreement shall terminate as of the date such litigation or claim is filed or instituted. You will indemnify and hold harmless Meta from and against any claim by any third party arising out of or related to your use or distribution of the Research Materials.

6. Term and Termination. The term of this Agreement will commence upon your acceptance of this Agreement or access to the Research Materials and will continue in full force and effect until terminated in accordance with the terms and conditions herein. Meta may terminate this Agreement if you are in breach of any term or condition of this Agreement. Upon termination of this Agreement, you shall delete and cease use of the Research Materials. Sections 5, 6 and 9 shall survive the termination of this Agreement.

7. Governing Law and Jurisdiction. This Agreement will be governed and construed under the laws of the State of California without regard to choice of law principles, and the UN Convention on Contracts for the International Sale of Goods does not apply to this Agreement. The courts of California shall have exclusive jurisdiction of any dispute arising out of this Agreement.

8. Modifications and Amendments. Meta may modify this Agreement from time to time; provided that they are similar in spirit to the current version of the Agreement, but may differ in detail to address new problems or concerns. All such changes will be effective immediately. Your continued use of the Research Materials after any modification to this Agreement constitutes your agreement to such modification. Except as provided in this Agreement, no modification or addition to any provision of this Agreement will be binding unless it is in writing and signed by an authorized representative of both you and Meta.

Acceptable Use Policy

Meta seeks to further understanding of new and existing research domains with the mission of advancing the state-of-the-art in artificial intelligence through open research for the benefit of all.

As part of this mission, Meta makes certain research materials available for use in accordance with this Agreement (including the Acceptable Use Policy). Meta is committed to promoting the safe and responsible use of such research materials.

Prohibited Uses

You agree you will not use, or allow others to use, Research Materials to:

 Violate the law or others’ rights, including to:
Engage in, promote, generate, contribute to, encourage, plan, incite, or further illegal or unlawful activity or content, such as:
Violence or terrorism
Exploitation or harm to children, including the solicitation, creation, acquisition, or dissemination of child exploitative content or failure to report Child Sexual Abuse Material
Human trafficking, exploitation, and sexual violence
The illegal distribution of information or materials to minors, including obscene materials, or failure to employ legally required age-gating in connection with such information or materials.
Sexual solicitation
Any other criminal activity

Engage in, promote, incite, or facilitate the harassment, abuse, threatening, or bullying of individuals or groups of individuals

Engage in, promote, incite, or facilitate discrimination or other unlawful or harmful conduct in the provision of employment, employment benefits, credit, housing, other economic benefits, or other essential goods and services

Engage in the unauthorized or unlicensed practice of any profession including, but not limited to, financial, legal, medical/health, or related professional practices

Collect, process, disclose, generate, or infer health, demographic, or other sensitive personal or private information about individuals without rights and consents required by applicable laws

Engage in or facilitate any action or generate any content that infringes, misappropriates, or otherwise violates any third-party rights, including the outputs or results of any technology using Research Materials

Create, generate, or facilitate the creation of malicious code, malware, computer viruses or do anything else that could disable, overburden, interfere with or impair the proper working, integrity, operation or appearance of a website or computer system

2. Engage in, promote, incite, facilitate, or assist in the planning or development of activities that present a risk of death or bodily harm to individuals, including use of research artifacts related to the following:

Military, warfare, nuclear industries or applications, espionage, use for materials or activities that are subject to the International Traffic Arms Regulations (ITAR) maintained by the United States Department of State

Guns and illegal weapons (including weapon development)

Illegal drugs and regulated/controlled substances
Operation of critical infrastructure, transportation technologies, or heavy machinery

Self-harm or harm to others, including suicide, cutting, and eating disorders
Any content intended to incite or promote violence, abuse, or any infliction of bodily harm to an individual

3. Intentionally deceive or mislead others, including use of research materials related to the following:

 Generating, promoting, or furthering fraud or the creation or promotion of disinformation
 Generating, promoting, or furthering defamatory content, including the creation of defamatory statements, images, or other content

Generating, promoting, or further distributing spam

 Impersonating another individual without consent, authorization, or legal right

Representing that outputs of research materials or outputs from technology using Research Materials are human-generated

Generating or facilitating false online engagement, including fake reviews and other means of fake online engagement

4. Fail to appropriately disclose to end users any known dangers of your Research Materials.
```

---

## 5. What this notice does not cover

These remain peripheral. They keep their own tool licenses and are **not** promoted to Essential by this notice:

- ComfyUI
- Qwen image and Qwen Image Edit families
- FLUX local families
- V-JEPA / World Intelligence (advisory same-world check; it does not generate Spatial Map geometry)

---

## 6. How to review this notice later

Open Setup in Adept UI. The Essential Components notice stays available after you agree. Optional About / Licenses links, when present, must load this same versioned document from the Adept API — not a second competing file.
