# Agile Maturity Assessment Framework

A lightweight framework for assessing a team's agile maturity across four
dimensions. It's meant to open a coaching conversation, not to produce a
score for its own sake — the number matters less than the discussion it
starts.

## Overview

Run the assessment quarterly with each team, ideally as a facilitated
workshop rather than a survey people fill out alone. Score each dimension
from 1 (ad hoc) to 5 (optimizing), and capture one concrete example for
every score the team disagrees on — those disagreements are usually more
useful than the average.

## Dimension: Team Autonomy

Measures how much a team can plan, build, test, and ship without
escalating routine decisions outside the team.

- **1 — Ad hoc:** Most decisions, including small technical ones, require
  sign-off from someone outside the team.
- **3 — Defined:** The team owns its sprint scope and technical approach,
  but cross-team dependencies routinely block delivery.
- **5 — Optimizing:** The team resolves cross-team dependencies proactively
  and rarely needs an escalation path at all.

## Dimension: Flow Metrics

Measures whether the team can see and act on its own delivery data —
cycle time, throughput, and work-in-progress — rather than relying on
velocity alone.

- **1 — Ad hoc:** No cycle time or throughput tracking; velocity is the
  only metric anyone looks at.
- **3 — Defined:** Cycle time and WIP limits are tracked and reviewed in
  retrospectives, but the team doesn't yet act on the trends between
  retros.
- **5 — Optimizing:** The team adjusts WIP limits and swarms on aging work
  mid-sprint based on live flow data.

## Dimension: Technical Practices

Measures the engineering practices that let a team ship frequently without
accumulating risk — automated testing, CI/CD, trunk-based development,
and observability.

- **1 — Ad hoc:** Manual testing and manual deploys; releases are
  infrequent and treated as risky events.
- **3 — Defined:** Automated test suite and CI exist, but deploys are
  still batched and scheduled rather than continuous.
- **5 — Optimizing:** Every merge to main can ship; the team relies on
  feature flags and observability instead of large pre-release test
  cycles.

## Dimension: Stakeholder Collaboration

Measures how directly the team engages with the people who use or are
affected by what it builds, versus working through intermediaries.

- **1 — Ad hoc:** Requirements arrive as a finished spec; the team has no
  direct contact with end users or business stakeholders.
- **3 — Defined:** Product owner represents stakeholder needs; the team
  sees user feedback secondhand, on a delay.
- **5 — Optimizing:** The team regularly observes real usage or talks
  directly to users, and adjusts the backlog based on what it learns.

## Scoring Guide

Average the five dimension scores, but present the range and the specific
examples alongside the average — a team scoring "3, 3, 3, 3, 3" is in a
very different place than one scoring "1, 5, 3, 1, 5," even though both
average to 3. Use the low scores to pick the coaching focus for the next
quarter rather than trying to move every dimension at once.
