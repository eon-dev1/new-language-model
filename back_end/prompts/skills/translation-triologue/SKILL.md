---
name: translation-triologue
description: A 3-role, society of thought, structured analytical conversation flow for NLM platform work. Every claim must be justified, every uncertainty explicit, every corpus lookup logged. Applies to translation decisions, corpus analysis, grammar documentation, dictionary building, or any other task.
---

# Triologue — Structured Analytical Workflow

**Core principle**: Rigorous analytical work requires three types of justified claim — a primary claim, a probing challenge, and a process validation. Each must be explicit with traceable reasoning. Unjustified assertion is the primary failure mode this workflow prevents.

This protocol applies to **any task** on the NLM platform: translation decisions, corpus pattern analysis, grammar documentation, dictionary definition, data quality review, or any other analytical work.

Merely performative analysis restates without updating. Productive session will have each roundtable member change the context window at each turn. 

---

## Activation

**Your first response in a triologue session must:**

1. Open with `## Translation Discussion Begins`
2. State the task type (e.g. translation / corpus analysis / grammar documentation / dictionary definition / other)
3. Name how each role (Linguist, Analyst, Auditor) applies to this specific task
4. Begin the deliberation immediately

Do not produce free-form analysis first and shift to triologue later. The triologue IS the analysis. If the task requires preliminary data gathering (tool calls), run those within the triologue structure — Linguist cites them, Analyst challenges them, Auditor validates they were done.

---

## The Three Roles

### Linguist — Primary Claim (leads)
Makes the central claim or proposal. States: what the evidence shows, the reasoning behind the interpretation, and why this conclusion over alternatives. Cites sources and DB lookups. Makes the working call on disputes — but Auditor can escalate.

### Analyst — Receiving Claim
Provides constructive, productive adversarial questions, for whether the proposal holds from the application or receiving side. 

### Auditor — Process Claim
Validates that the other two claims were adequately made. Rates confidence and types uncertainty. Can block and require revision. Does not certify content correctness — certifies **process transparency**. Low/Uncertain findings cannot pass silently.

---

## Confidence Ratings

| Rating | Criteria |
|--------|----------|
| **High** | Primary claim well-supported; receiving-side fit confirmed; consistent with prior decisions; DB evidence is human-verified |
| **Medium** | One area of uncertainty — primary claim approximate, receiving-side fit approximate, or DB evidence is unverified |
| **Low** | Disputed interpretation, no clear receiving-side fit, significant gaps, or only unverified DB entries available |
| **Uncertain** | Foundational gap — insufficient data, unknown territory, or missing context that makes any claim premature |

DB evidence from unverified entries (`human_verified: false`) cannot push a rating above **Medium** on its own.

**Uncertainty type tags** (append to Low/Uncertain):
`[EVIDENCE]` `[INTERPRETATION]` `[CULTURAL]` `[CONSISTENCY]` `[DATA]`

- `[EVIDENCE]` — insufficient corpus support for the claim
- `[INTERPRETATION]` — the claim is one reading among plausible alternatives
- `[CULTURAL]` — cultural or community knowledge required that is not in the DB
- `[CONSISTENCY]` — conflicts with an established prior decision
- `[DATA]` — required data is missing, sparse, or entirely unverified

---

## Database Tools

Tool calls replace asserted corpus knowledge with verified corpus knowledge. They are **mandatory when making claims about the corpus** (word usage, existing translations, dictionary entries, grammatical patterns). They are optional when reasoning from linguistic knowledge alone.

Any member may call any relevant tool. Each call must be logged inline:

```
[Role] → DB: tool_name(params)
Result: [1–3 sentence summary]
Verified: [all / mixed / none — whether returned entries carry human_verified: true]
Impact: [how this changes the claim — or "Confirmed. No change."]
```

**Verification weight**:
- `human_verified: true` — reviewed by a human. Can be cited as positive evidence.
- `human_verified: false` — not yet reviewed. Treat as a data point, not an authority. Cannot raise confidence on its own; can inform but not confirm.

A tool result that contradicts the proposal must be addressed before PASS is issued.

---

## Protocol

The sequence below is the default. It is not a law — follow the deliberation, not the steps.

### 1. Input
```
Subject: [what is being analyzed, decided, or produced]
Context: [language / domain / corpus / current view — relevant environment]
Task type: [translation / corpus analysis / grammar documentation / definition / other]
```

### 2. Linguist proposes
```
Proposal: [the claim, translation, definition, or finding]
Evidence: [source citations, corpus data, or reasoning basis]
Reasoning: [why this interpretation over alternatives]
[DB call if making a corpus claim]
```

### 3. Analyst probes
```
[1–3 questions or challenges from a productively adversarial perspective]
[DB call if needed — if the result resolves the question, state that instead of asking it]

Linguist responds: [answers challenge; revises proposal if warranted]
[DB call if response requires corpus verification]
```

### 4. Auditor validates
```
Evidence cited: [confirmed / not confirmed — if not, block]
Justification: [sufficient / needs expansion / insufficient — if insufficient, block]
[DB call if making a consistency check]
Confidence: [High / Medium / Low / Uncertain]
Uncertainty type: [tag or none]
Concerns: [flagged issues]
Status: [PASS / REVISE / ESCALATE → path]
```

### 5. Write to database

Runs after Auditor issues **PASS**. Skipped entirely on REVISE or ESCALATE.

Before invoking any write tool, present the proposed write and any uncertainties to the translator for review. The approval gate allows inline editing before execution.

All writes use `human_verified: false` unless the cycle concluded with High confidence and no concerns.

**Check for blocking conditions before writing:**

#### Hard blocks — always require human confirmation
- **Overwrite conflict**: an existing entry is `human_verified: true`. State the conflict and existing content; do not write.
- **Key decision establishment**: the cycle established a new term or rule that will bind future work. Confirm with the human before locking it in.
- Do these BEFORE invoking the write tools. 


#### Proceed without asking
- Confidence High or Medium, no concerns, no human-verified entry conflicts


### 6. Escalation paths

| Path | Uncertainty type | Action |
|------|-----------------|--------|
| Consistency Check | CONSISTENCY | Cross-reference prior decisions; resolve or update |
| Additional Evidence | EVIDENCE | Gather more corpus data before concluding |
| Community Check | CULTURAL | Provisional; defer to mother-tongue or domain expert review |
| Expert Review | INTERPRETATION with high stakes | Flag; do not finalize |
| Defer | DATA | Mark incomplete; continue adjacent material |

---

## Output

**Key decision entry** (produce when a new term, rule, or binding decision is established):
```
Decision: [the established term, definition, or rule]
Domain: [e.g., grammar, glossary, translation pattern]
Basis: [evidence and reasoning]
Established: [subject reference] | Confidence: [rating]
Notes: [caveats, scope limits, review flags]
```

Established key decisions are binding for consistency. The Auditor cross-references prior decisions every cycle.

---

## Anti-Patterns

| Anti-Pattern | Symptom | Fix |
|--------------|---------|-----|
| **Deferred activation** | Triologue offered as future option rather than current mode | First response must open with `## Translation Discussion Begins` |
| **Unjustified assertion** | Claim made without evidence, reasoning, or DB verification for corpus claims | Block; require justification |
| **Role collapse** | Analyst duplicates Linguist's reasoning instead of probing the other side | Redirect to receiving-side perspective |
| **Confidence theater** | Auditor defaults to High without explicit evaluation | Require uncertainty type check every cycle |
| **Data without response** | DB result logged; deliberation continues unchanged | Every result must update or explicitly confirm reasoning |
| **Corpus claim without lookup** | "This pattern is consistent" asserted without DB verification | Corpus claims require tool verification |
| **Treating unverified as verified** | Auditor rates High based solely on `human_verified: false` entries | Unverified entries inform; they do not confirm. Cap at Medium. |
| **Silent overwrite** | Writes without checking for existing human-verified entries | Always check before writing; hard-block on conflicts |
| **Write on REVISE/ESCALATE** | Writes to DB before the cycle has resolved | Only write on PASS |
| **Skipping the write** | PASS issued but no DB write follows | If PASS and no blocking conditions, writing is part of completing the cycle |

---
