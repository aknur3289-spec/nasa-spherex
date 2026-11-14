# AI use

- Codex implemented the React viewer and responsive interface, generated synthetic fixtures, and added and ran tests.
- Claude produced the team’s master strategy PDF, which informed the project concept, technical plan, algorithms, and success criteria.

## Science module
- OpenAI Codex agents (one git worktree per task) wrote pipeline/poc code: dial builder, contract check,
  detectability figures, observing windows, real-data PoC scripts, slide figures.
- Claude (Anthropic) designed prompts, wrote and validated the geometry core (pipeline/spx/geometry.py,
  focus.py, detectability.py, horizons.py), reviewed every agent result and checked all numbers.
- Every scientific number is reproducible from scripts and recorded in docs/EXPERIMENTS.md; synthetic data
  is labelled `provenance.synthetic = true` and shown as DEMO DATA. No AI-generated images.
