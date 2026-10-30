# ADR: Hard-cheese stays the quiz; a review artifact carries understanding

**Status:** accepted (2026-10-18; placement 2026-10-22)

Hard-cheese stays the comprehension quiz at publication time.
A separate review artifact carries the shape of the change, the expectations, and the why through the work.

## Context

Fork I in the manifesto evidence (#829) asked what hard-cheese becomes.
PR #829 offered "becomes the review-time brief, or parks".
PR #828 asked hard-cheese to "support understanding throughout the work, not surprise the user with an exam at publication".
[hard-cheese-retained-001](./hard-cheese-retained-001.md) allows retirement only with consumer-population evidence.

No reachable primary study measures a defect-detection effect of author-written descriptions.
Bosu, Greiler, and Bird (2015) found that useful-comment density falls as the number of files per change rises.
Copilot, CodeRabbit, GitLab Duo, and Graphite all draft an author-editable pull request description.
The review artifact is therefore justified by comprehension and review cost, not by defect detection.

## Decision

- Hard-cheese does not change its role. It stays a quiz.
- Understanding throughout the work belongs to the review artifact, not to hard-cheese checkpoints.
- A follow-up `/mold` designs the review artifact: its sections, who edits it, and where it lands.

The prior leaning for that mold: a Review artifact (see [workflow-contract-milknado-seam-007](./workflow-contract-milknado-seam-007.md)) is the single source, and plate renders it into the pull request body.
Plate's pull request body already has Non-obvious changes and Diagram sections.

## Source

Owner rulings of 2026-10-18 (fork I) and 2026-10-22 (option A), recorded in Wheypoint `tenet-reconciliation-rulings` and in #832.
