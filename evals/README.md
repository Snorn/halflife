# Evals

`tests/` proves the machinery works. This proves the *output* is worth reading, which is the
actual risk in step 1.

```bash
python evals/run_evals.py depth
python evals/run_evals.py continuity
python evals/run_evals.py all
```

These make real API calls. Cases live in [cases.yaml](cases.yaml); pick topics you can personally
judge, because the numbers below are a pointer to where to look, not a verdict.

Every run writes the generated text to `evals/output/<suite>-<timestamp>/`. Read it.

## depth

Generates issue 1 of a fresh, unplanned series for each topic at each depth, so depth is the only
variable. Then two checks:

* **Inferred depth.** A judge is given the piece and the rubric and asked which level it was
  written to. Reports accuracy and, more usefully, **mean signed error** — the failure mode this
  is built to catch is collapse toward depth 3, which shows up as negative drift on high depths
  and positive drift on low ones, even when accuracy looks acceptable.
* **Disjointness.** The rubric claims two levels apart should be different pieces, not one nested
  in the other. The lowest and highest depths for each topic are compared for re-explanation.

If depth is not holding, the fix is the rubric text in
`src/halflife/generation/prompts/depth_rubric.py` — bump `DEPTH_RUBRIC_VERSION` when you change
it, so deliveries generated before and after are distinguishable.

## continuity

Generates one series straight through, feeding the real ledger forward. Two checks:

* **Near-duplicate coverage points**, by token Jaccard over the ledger. Cheap, deterministic, and
  catches the ledger filling up with restatements.
* **Does the last issue re-teach the first**, judged. Referring back in a clause is correct;
  explaining it again is not, and the judge is told the difference.

Exit code is non-zero when anything fails, so these can be wired into CI later — but for now the
point is that you run them after changing a prompt and compare against the previous run's output
directory.

## What is deliberately not measured

Whether the content is *correct*. A judge model is not a subject-matter expert on SAP Web
Dispatcher, and pretending otherwise would give a number that feels like accuracy and is not.
That check is you, reading your own daily issues — which is why step 1 exists before anything
else does.
