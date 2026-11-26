# Specification Quality Checklist: 006-flow-catalog

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-26
**Feature**: [spec.md](../spec.md)

## Content Quality

- [ ] No implementation details (languages, frameworks, APIs)
- [ ] Focused on user value and business needs
- [ ] Written for non-technical stakeholders
- [ ] All mandatory sections completed
- [ ] Written in Simplified Technical English (principle X)

## Requirement Completeness

- [ ] No [NEEDS CLARIFICATION] markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Success criteria are measurable
- [ ] Success criteria are technology-agnostic (no implementation details)
- [ ] All acceptance scenarios are defined
- [ ] Edge cases are identified
- [ ] Scope is clearly bounded
- [ ] Dependencies and assumptions identified

## Feature Readiness

- [ ] All functional requirements have clear acceptance criteria
- [ ] User scenarios cover primary flows
- [ ] Each of the ten flows has a goal, steps, tags, gates, artifacts, failure behaviour, and an acceptance test
- [ ] Feature meets the measurable outcomes in Success Criteria
- [ ] No implementation details leak into the specification

## Notes

- The spec names some file formats and function names because the owner asked for template file specs. These are contract details, not product code.
- The `hop` limit of 5 for a verified template is a rule of constitution v1.3.0. No deviation and no Complexity Tracking row. The functions for source, limit, exclusion, branch, gate, and dialog are spec 003 code. `core/flows.py` has no copy (SC-014).
- Items stay unchecked until task T063.
