# jev-combined protocol profile

A packaged protocol profile for open research questions. It asks every author for exactly one testable hypothesis, and it turns the J1 gate on (`j1.enforce: true`) with the combined jev rules described in the main README (§3).

## Use

```bash
reasonlineage run my-question.json --protocol jev-combined
```

- Leave `candidates` out of the task. The profile ranks exactly one item, the hypothesis title (`answer.open_question_items` is `[1, 1]`).
- The setup must give the task a jev checker (`checker_for`). In experiment mode, a run whose protocol turns the J1 gate on does not start without a checker.
- `run` records the profile in `header.json`, so `resume`, `diagnose` and `--replay` reuse it.

## Input contract

The prompts treat the task's `question` as a research question followed by a frozen evidence packet:

- `prompts/seed.md` introduces it as "Research question and frozen evidence packet".
- `prompts/author_system.md` asks authors to cite the supplied source labels `[S1]`–`[S4]`, and to mark anything outside the packet as unverified prior knowledge.
- The J1 premise questions ask whether a premise is supported by the supplied packet.

Put the evidence packet, with its sources labelled `[S1]` to `[S4]`, into the `question` text. Without it, authors are asked to cite labels that do not exist, and the premise check tends to report a gap.

## Keys kept for continuity

`protocol.json` is unchanged from the study that produced it, so its hash still identifies that study. `reasonlineage run` does not read these keys:

- `answer.length_enforcement`;
- the whole `pilot` block: panel size, call limits, checker choice, population sizes, and calibration hash.

The setup file decides the panel and the checker. The engine sizes the population from the active roster, and there is no call cap.
