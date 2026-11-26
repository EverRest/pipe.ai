# Specification Quality Checklist: 004-delegation

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-25
**Updated**: 2026-11-26
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Model Alignment (constitution v1.3.0, spec 003)

- [x] A step is `{agent, capability, access, goal}` (`agent` may be `any` with `capability: tag:<tag>`). No `kind: delegate`, no `kind: code`, no `skill`, and no other step-type enum (FR-001).
- [x] The spec uses `phase`, `access`, and `next: {agent, access, payload}` only.
- [x] The core is capability-agnostic. Worktree, git, deny rules, and MR creation belong to the `claude` adapter and a replaceable provider (FR-013, FR-018).
- [x] The owner gate follows decision Q6 of spec 003: 004 adds the gate for `write` steps (FR-004, FR-005). The `read` case has no gate (DQ1 of plan.md, FR-008).
- [x] The allowlist shape is generic (bot IDs and user IDs), so spec 005 can reuse it (FR-009).
- [x] Spec 003 rules stay: the `hop` limit by plan source (3 free, 5 verified template), the claim rule, the timeout with "Retry", and the catch-up (FR-017).

## Notes

- All items pass.
- Tool names (Slack, GitLab) name the product surface from the design brief. GitLab is the first MR provider and is replaceable.
- The owner decisions DQ1 to DQ8 are in the section "Design decisions" of plan.md. The spec states each one.
- Pass 2 (constitution 1.3.0): FR-024 (`effective_deny_rules`), FR-025 (`step_rejected`), the type 4 versus type 5 wording, and the open questions O1 and O2 in plan.md.
- Added by DQ3: FR-019, FR-020 (the `target` and the map `delegate_repos`). Added by DQ5 to DQ7: FR-021, FR-022.
