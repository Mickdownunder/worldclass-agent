# Wiring Audit: June, Operator, ARGUS, ATLAS

## Audit Goal

Identify what currently prevents the system from operating as the best research-agent system in the world.

This audit focuses on:

1. state ownership
2. trigger authority
3. canonical path discipline
4. duplicate decision centers
5. contract integrity

## Executive Summary

The system already contains unusually strong components:

- a real research state machine in Operator
- durable evidence and phase progression
- a mission layer in June
- deterministic execution via ARGUS
- proof / sandbox validation via ATLAS

The main weakness is **control-plane sovereignty**.
The architecture is powerful, but authority is still partially distributed across several subsystems.

## Findings

### P0: Split-brain global control

Current decision-capable centers include:

- June mission control
- Operator Brain
- Conductor
- Council
- UI-triggered direct execution paths

This creates the risk that multiple subsystems decide "what should happen next" at different levels without a single canonical owner.

### P0: Multiple ingress paths

Observed ingress paths:

- OpenClaw / June commands
- UI actions in `ui/src/lib/operator/actions.ts`
- direct operator job creation
- background follow-up / council / orchestrator paths
- post-run Brain trigger from `workflows/research-phase.sh`

A worldclass system requires a single canonical ingress for externally meaningful work.

### P0: Mixed truth surfaces

Truth is currently spread across:

- June mission artifacts
- Operator project state
- progress files
- quality gates
- ad-hoc signal file `knowledge/last_research_complete.json`
- memory-derived planning state

This makes the system harder to reason about under autonomy.

### P1: Hidden autonomy path after research completion

`workflows/research-phase.sh` triggers a background Brain cycle after a run completes.

This is architecturally dangerous because:

- a local workflow completion can trigger higher-level planning
- June may no longer be the sole global orchestrator
- the next action can emerge from an implicit side effect rather than the main control plane

Recommendation:

- replace this direct Brain trigger with a typed completion event
- June or a policy-owned dispatcher should consume the event

### P1: UI bypasses the cleanest control plane

`ui/src/lib/operator/actions.ts` directly starts `run-research-cycle-until-done.sh` for project continuation.

This is operationally useful but architecturally suboptimal because the UI becomes a semi-independent orchestrator.

Recommendation:

- UI should submit intents into the same canonical control plane used by June
- UI should be a client, not an alternate executive surface

### P1: Brain is too close to peer status with June

`lib/brain.py` is powerful enough to act like a second strategist.

This is not inherently wrong, but in the target architecture Brain must be:

- internal to Operator
- advisory or policy-bound
- non-competing with June for global authority

### P1: Conductor and Council need narrower boundaries

Conductor and Council are strong subsystems, but they must remain narrow:

- Conductor: only intra-project routing
- Council: only terminal review and branching

If they are allowed to act like portfolio-level planners in parallel, the system loses sovereignty.

### P2: ARGUS and ATLAS are the cleanest part of the hierarchy

The June -> ARGUS -> ATLAS chain is comparatively coherent.

Why:

- deterministic execution paths
- machine-readable contract outputs
- durable logs
- clear validation boundary

This chain should be used as the architectural standard for the broader control plane.

## Current Ownership Map

### June

Currently owns in practice:

- mission compilation
- mission execution state
- mission decisions
- delegation into ARGUS
- user-facing orchestration

### Operator

Currently owns in practice:

- research project lifecycle
- phase control
- progress tracking
- evidence, sources, findings, reports
- quality gates
- background orchestration logic via Brain / Council / Conductor

### ARGUS

Currently owns in practice:

- bounded macro execution
- local execution logs
- result summarization for June

### ATLAS

Currently owns in practice:

- sandbox policy checks
- proof / disproof execution
- validation artifacts

## Current Trigger Map

### External / user-level

- Telegram -> June / OpenClaw bridge
- UI -> Operator actions

### Internal / system-level

- research completion -> Brain cycle
- terminal project -> Council
- follow-up generation -> child projects
- Conductor gating -> alternate phase progression

## Canonical vs Legacy / Parallel Paths

### Should be canonical

- external tasks -> June
- epistemic project truth -> Operator
- deterministic proof -> ARGUS / ATLAS

### Currently parallel or ambiguous

- UI direct lifecycle execution vs mission-centric execution
- Brain continuation vs June continuation
- ad-hoc signal files vs typed event flow
- operator-local autonomy vs June-owned global orchestration

## Contract Gaps

### Gap 1: No single unified command schema

June mission commands, operator workflow requests, and research-state transitions are related but not yet one formalized contract family.

### Gap 2: No single unified completion event schema

Research completion currently propagates through a combination of:

- project state
- signal file
- background Brain trigger
- logs

This should become one typed completion event.

### Gap 3: Global next action not strictly owned by one layer

The system can currently derive a next action from:

- June mission runtime
- Brain reasoning
- Conductor gate
- Council proposal

These need formal boundaries.

## Required Architecture Decisions

### Decision 1

June is the only global orchestrator.

### Decision 2

Operator is the only epistemic truth substrate.

### Decision 3

Brain cannot autonomously become a second global planner. It must operate under policy or emit proposals/events.

### Decision 4

Conductor cannot leave project-local scope.

### Decision 5

Council cannot become a continuous parallel planner; it is terminal review and branching only.

### Decision 6

UI cannot remain a bypass orchestration surface. It must become a client of the canonical control plane.

### Decision 7

All completion, continuation, and follow-up logic must move to typed event contracts.

## Refactor Priorities

### P0

Freeze and document authority hierarchy.

### P0

Define the canonical ingress and continuation path.

### P0

Remove or subordinate hidden post-run autonomy triggers.

### P1

Introduce unified typed contracts for command, state, evidence, gate, and decision exchange.

### P1

Migrate UI and other direct execution surfaces to the canonical control plane.

### P1

Convert ad-hoc signal files into structured event records.

### P2

Strengthen observability so every autonomous continuation is attributable to a single authority and correlation id.

## Concrete First Refactors

1. stop treating `knowledge/last_research_complete.json` as a control-plane signal; replace it with a structured event log or queue
2. remove direct Brain-cycle launch from `workflows/research-phase.sh`; emit a completion event instead
3. route UI research actions through the same canonical orchestration surface used by June
4. formalize `TaskIntent`, `MissionSpec`, `OperatorCommand`, `ResearchProjectState`, `EvidenceBundle`, `GateResult`, `DecisionResult`
5. explicitly classify every existing path as canonical, temporary, or deprecated

## End State

The wiring is considered worldclass-ready when:

- June is unquestionably the global orchestrator
- Operator is unquestionably the epistemic machine
- Brain, Conductor, and Council are powerful but bounded subsystems
- ARGUS and ATLAS serve as disciplined execution and proof layers
- every important action is contract-backed, observable, and attributable
- no part of the system can silently fork the control plane
