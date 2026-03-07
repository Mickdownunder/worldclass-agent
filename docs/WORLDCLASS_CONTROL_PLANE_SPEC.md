# Worldclass Control Plane Spec

## Purpose

This document defines the target control-plane architecture for the system with a single standard:
**build the best research-agent system in the world**.

The system must not merely be capable. It must be sovereign, epistemically hard, reproducible,
and architecturally coherent under autonomous operation.

## Non-Negotiable Goal

The system must:

- understand user intent robustly through June
- execute research through Operator without epistemic drift
- validate claims through ARGUS and ATLAS with durable evidence
- avoid hallucination by grounding action in machine state, artifacts, and gates
- produce discoveries, invention candidates, and follow-up programs through disciplined autonomy

## Core Principle

The system is one sovereign machine with specialized layers.
It is not a loose federation of agents with overlapping authority.

## Authority Hierarchy

### 1. June

June is the **only global orchestrator**.

Responsibilities:

- receive all external user tasks
- normalize intent
- manage mission state and tasking state
- decide global next action
- route work into Operator, ARGUS, ATLAS
- report back to the user in understandable form

June must not invent truth.
June may orchestrate, interpret, and prioritize, but truth must come from Operator state and hard evidence.

### 2. Operator

Operator is the **only epistemic source of truth**.

Responsibilities:

- own research project lifecycle
- own evidence state
- own quality gates
- own reports, findings, sources, verification outcomes
- own durable progress and research status
- own scientific / technical state transitions

If June and Operator disagree, Operator wins.

### 3. Brain

Brain is an **internal analytic and planning subsystem of Operator**.

Responsibilities:

- analyze current operator state
- propose next action
- reflect on outcomes
- improve internal planning through memory

Brain is not a second global orchestrator.
Brain must not compete with June for global control authority.

### 4. Conductor

Conductor is an **intra-project controller**.

Responsibilities:

- decide phase-local routing within a research project
- determine whether a project should search more, read more, verify, or synthesize
- never become a global task owner

Conductor must not own portfolio-level or user-facing orchestration.

### 5. Council

Council is a **terminal-state meta-review and branching subsystem**.

Responsibilities:

- assess completed or terminal projects
- generate follow-up directions
- branch into child projects or broader programs

Council must not act as a continuous global planner in parallel to June.

### 6. ARGUS

ARGUS is a **deterministic execution specialist under June**.

Responsibilities:

- execute bounded research macros
- gather durable artifacts
- return structured results and recommendations
- request ATLAS validation when required

### 7. ATLAS

ATLAS is a **proof and validation subsystem under June via ARGUS**.

Responsibilities:

- execute validation and sandbox checks
- run proof/disproof code in a constrained environment
- return structured gate results

## Source of Truth Model

### June owns

- mission identity
- mission task graph
- delegation records
- user-facing execution objective
- orchestration decision state

### Operator owns

- project.json
- progress.json
- evidence, findings, reports, sources
- quality gate results
- research lifecycle status
- terminal and non-terminal project transitions

### ARGUS / ATLAS own

- execution logs
- sandbox logs
- validation summaries
- envelope outputs for June consumption

### OpenClaw owns

- sessions
- channel bindings
- agent runtime presence

OpenClaw does **not** own domain truth.

## Trigger Authority Rules

### Allowed external ingress

All external tasks must enter through June.

Examples:

- Telegram -> June
- UI -> June-facing control plane
- API -> June-facing control plane

### Allowed internal triggers

Operator subsystems may emit:

- events
- proposals
- branch recommendations
- local phase transitions

Operator subsystems must not silently create parallel global orchestration loops.

### Hard rule

No subsystem may bypass June to become a second user-facing or portfolio-facing orchestrator.

## Canonical Control Paths

### Path A: External task intake

User -> June -> Mission compile -> Operator command / ARGUS delegation / ATLAS validation -> result -> June report

### Path B: Research project lifecycle

June -> Operator create/advance project -> research phase execution -> evidence + gates -> June consumes machine result

### Path C: Validation / proof path

June -> ARGUS -> ATLAS -> evidence bundle / gate result -> June decision

### Path D: Follow-up generation

Operator terminal project -> Council proposal/event -> June decides global action -> Operator creates new project if approved by policy

## Forbidden Patterns

The following patterns are explicitly forbidden in the target architecture:

- multiple global planners acting concurrently without a clear authority chain
- UI-specific bypass paths that skip the canonical mission/control plane
- ad-hoc file signals as primary orchestration truth
- background autonomy that creates new global work without explicit authority
- human-language-only handoffs instead of typed contracts
- using June prose as truth instead of machine state and evidence

## Required Control Contracts

The system must converge on a typed contract set.

### TaskIntent

Fields:

- intent_id
- user_request
- normalized_intent
- risk_level
- scope
- constraints

### MissionSpec

Fields:

- mission_id
- objective
- owner
- delegated_subsystems
- success_criteria
- allowed_actions
- runtime_budget

### OperatorCommand

Fields:

- command_id
- command_type
- project_id
- payload
- issued_by
- correlation_id

### ResearchProjectState

Fields:

- project_id
- phase
- status
- quality_gate
- evidence_status
- council_status
- next_operator_action
- updated_at

### EvidenceBundle

Fields:

- evidence_id
- project_id
- artifact_paths
- summary
- metrics
- contradictions
- confidence

### GateResult

Fields:

- gate_id
- gate_type
- status
- fail_code
- reasons
- evidence_refs

### DecisionResult

Fields:

- decision_id
- owner
- mission_id or project_id
- next_action
- rationale
- required_followups

## Operational Invariants

The worldclass system must maintain these invariants:

1. there is exactly one global orchestrator
2. there is exactly one epistemic truth substrate
3. every important transition leaves durable artifacts
4. every autonomous continuation is attributable to a typed event or policy
5. every promotion-level recommendation is gate-backed
6. every subsystem can be reasoned about by contract, not folklore

## Acceptance Criteria

The control plane is considered worldclass-ready only when:

- all external ingress paths resolve to one canonical orchestration surface
- all research lifecycle transitions resolve to Operator truth
- Brain, Conductor, and Council no longer compete for global control
- ARGUS and ATLAS return typed machine-usable outputs only
- June decisions are fully grounded in Operator state and gate outputs
- no hidden autonomy path exists outside the defined hierarchy

## Migration Principle

The migration must prefer sovereignty over convenience.

If a path is useful but creates ambiguity, it must be:

- formalized
- subordinated
- or removed
