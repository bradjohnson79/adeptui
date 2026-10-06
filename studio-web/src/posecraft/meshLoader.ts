/** Resolve a Babylon loader extension from the stored filename, not a /file URL. */

const EXT_BY_NAME: Record<string, string> = {
  glb: ".glb",
  gltf: ".gltf",
  obj: ".obj",
};

export function pluginExtensionForAsset(filename: string | null | undefined, kind?: string | null): string {
  const lower = String(filename || "").toLowerCase();
  const match = lower.match(/\.([a-z0-9]+)$/);
  if (match && EXT_BY_NAME[match[1]]) return EXT_BY_NAME[match[1]];
  if (kind === "mesh-3d" || kind === "glb") return ".glb";
  return ".glb";
}

export function humanoidBoneHints(boneName: string): string | null {
  const n = boneName.toLowerCase();
  const table: Array<[RegExp, string]> = [
    [/hip|pelvis/, "pelvis"],
    [/spine(?!.*\d*[2-9])|spine_01|spine1/, "spine"],
    [/chest|spine_02|spine2|spine_03/, "chest"],
    [/neck/, "neck"],
    [/head/, "head"],
    [/left.*(shoulder|clavicle)|shoulder_l|upper_arm\.l|upperarm_l/, "leftShoulder"],
    [/left.*(elbow|forearm|lowerarm)|lower_arm\.l/, "leftElbow"],
    [/left.*(hand|wrist)/, "leftWrist"],
    [/right.*(shoulder|clavicle)|shoulder_r|upper_arm\.r/, "rightShoulder"],
    [/right.*(elbow|forearm|lowerarm)|lower_arm\.r/, "rightElbow"],
    [/right.*(hand|wrist)/, "rightWrist"],
    [/left.*(upleg|thigh|upperleg)|thigh_l/, "leftHip"],
    [/left.*(leg|shin|calf|lowerleg)|shin_l/, "leftKnee"],
    [/left.*(foot|ankle)/, "leftAnkle"],
    [/right.*(upleg|thigh|upperleg)|thigh_r/, "rightHip"],
    [/right.*(leg|shin|calf|lowerleg)|shin_r/, "rightKnee"],
    [/right.*(foot|ankle)/, "rightAnkle"],
  ];
  for (const [pattern, joint] of table) {
    if (pattern.test(n)) return joint;
  }
  return null;
}
