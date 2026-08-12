# M42 Wave 4 — Editing Recipes (R1)

Built-in immutable recipes (project-saveable copies supported):

1. Remove Object
2. Replace Character Clothing
3. Fix Hands
4. Repair Face
5. Sky Replacement
6. Moonlight Grade
7. Concept Paintover
8. Poster Cleanup

Each stores operation, maskDefaults, recommendedWorkflowFamily, referenceRequirements, preserveToggles, outputPreset, promptTemplate.

API: /api/image-product/projects/{id}/recipes. Applying a recipe seeds ImageEditWorkspace / Co-Director propose fields; user may override before execute.

Gate: EditingRecipesOperational. Artifact: 
ecipes_results.json.
