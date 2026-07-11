# Content Planning and Presenter-Understanding Gates

Use this before slide code for new decks and broad redesigns. The purpose is
not to produce a long specification. It is to catch a beautiful but
unexplainable deck before layout work makes weak content expensive to change.

## The compact deck plan

Write one row per slide. Keep each cell to one sentence where possible.

| Field | Required content |
|---|---|
| Claim | The assertion the audience should leave with |
| Audience question | The question this slide answers now |
| Proof object | Figure, chart, equation, table, image, video, or direct evidence |
| Evidence source | File, code, paper, dataset, observation, or user statement |
| Incoming bridge | Why this claim follows from the previous slide |
| Outgoing bridge | What question or consequence makes the next slide necessary |
| Presenter status | `confirmed`, `needs explanation`, or `not applicable` with a reason |

Read only the claim and bridge columns in order before coding. They must form
one causal argument. If a new concept appears without a bridge, repair the
story now rather than hiding the jump in speaker narration.

## Presenter-understanding gate

AI-generated technical content is not ready merely because it is correct or
visually polished. For every scientific result, model, unfamiliar chart, or
non-obvious number, record:

- plain-language meaning
- what is directly observed versus inferred
- what the evidence supports and does not support
- likely audience question and a defensible answer
- the user's confirmation that they can explain it, when the user is the
  presenter

`confirmed` means the presenter has explicitly confirmed that they can explain
the claim and evidence; content being supplied or owned by the user is not a
substitute for that confirmation. `not applicable` is only for standalone
documents or genuinely non-technical slides and must include the reason.

If the presenter cannot yet explain an item, pause and offer three paths:

1. explain it from the source evidence;
2. simplify or reframe the slide;
3. remove or move it to the appendix.

Do not mark the slide complete and do not invent confidence on the user's
behalf. An agent may draft the explanation, but the presenter owns the final
understanding decision.

## Figure contract

Every figure or chart used as evidence needs four short answers:

1. What are the axes, units, conditions, and comparison groups?
2. What visual feature should the audience inspect?
3. What claim does that feature support?
4. What conclusion would be an overclaim?

Internal diagnostics are not automatically presentation figures. Translate
an optimization metric, debugging panel, or model-selection plot into an
audience question first. If the user cannot explain why the audience needs
the figure, omit it.

## Number provenance

Classify every claim-carrying number as one of:

- `measured`: obtained directly from an experiment or observation
- `literature`: taken from a cited external source
- `derived`: follows from an equation or stated calculation
- `fitted`: estimated by fitting data
- `calibrated`: chosen to reproduce a target behavior
- `assumed`: a modeling or planning assumption
- `illustrative`: a non-evidentiary example

Keep units and source beside the number in the plan. On the slide or in
speaker notes, disclose fitted, calibrated, assumed, and illustrative values
when their status affects interpretation. Never present a calibrated value as
a first-principles result.

## Scientific-model contract

For any live academic deck where a simulation or mathematical model carries a
claim, the slide set must let the audience reconstruct the model at the level
needed for that genre. This is strictest for progress meetings, where the full
contract below is mandatory. For conference talks, lectures, and journal
clubs, include the claim-bearing subset and route remaining detail to the
appendix or cited source rather than silently omitting it. The full contract is:

- equation of motion or update rule
- interaction, force, adhesion, alignment, and reaction rules that matter
- state variables and state transitions
- initial and boundary conditions
- observables and how they are computed
- parameter units and provenance
- known omissions and approximations

Do not dump every derivation onto the main slide. Show the equation or rule
that carries the claim, define symbols at first appearance, and place the
full derivation or parameter table in backup slides when needed.

## Speaker notes

For live academic decks, prepare notes early enough to expose understanding
gaps. Use short scan-friendly lines grouped as:

- message
- evidence to point at
- transition
- likely question

Do not write a paragraph that must be read verbatim. Do not put production
instructions or reveal cues on the visible slide. Carry each approved outgoing
bridge into the speaker notes. For a standalone deck, put the bridge into a
visible support line or make the title/body sequence self-explanatory.

## Completion gate

Before calling content ready:

- every content slide has one claim and one dominant proof object
- title plus bridges read as a coherent causal story
- every chart satisfies the figure contract
- every claim-carrying number has provenance and units
- technical-model requirements are either shown or deliberately routed
- all live technical presenter-status items are `confirmed`; every
  `not applicable` item has a valid standalone or non-technical reason

Unresolved items are discussion prompts, not details to conceal with design.
