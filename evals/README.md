# Evals

`tests/` proves the machinery works. This proves the *output* is worth reading, which is the
actual risk in step 1.

```bash
python evals/run_evals.py depth
python evals/run_evals.py continuity
python evals/run_evals.py distance --run evals/output/continuity-<stamp>
python evals/run_evals.py all
```

These make real API calls. Cases live in [cases.yaml](cases.yaml); pick topics you can personally
judge, because the numbers below are a pointer to where to look, not a verdict.

Every run ends with what it cost:

```
spend for this run:
  claude-opus-5  28 calls  74,300 in  41,900 out  $1.42
  total $1.42 over 28 calls ($0.051/call)
```

Costed per model actually used, so a server-side fallback is billed at its own rates rather than
the requested model's. Printed even when a run fails part way, so an interrupted run still tells
you what it spent. An unrecognised model reports tokens and no dollar figure rather than a wrong
one — if you change `HALFLIFE_MODEL_ID`, add it to `_PRICING` in
[run_evals.py](run_evals.py).

Rough scale at the time of writing: a depth run is 28 calls, plan-ab 15, continuity 9, distance 4
per series judged. Generating
one real issue for yourself is a single call — the evals are the expensive part, not the product.

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

## distance

Generation prompt v3 tells the writer to prefer an older ledger point over a recent one where both
would serve, on the grounds that a reader recalls something by having to use it. This suite says
whether that instruction does anything.

It judges *saved* output rather than generating: point it at a run directory and it maps every
place an issue builds on earlier ground back to the issue that established it, then reports the
distribution of distances. So a prompt revision can be measured against output produced weeks
earlier for the price of the judging alone. Pass `--run` twice to print both.

Read the distribution, not the mean. References cluster by issue — one issue can contribute
fifteen of them — so a six-issue series is nearer four independent observations than forty, and a
difference of a few tenths between runs is noise.

Runs record a `run.json` naming the prompt and rubric versions that produced them. Directories
predating that say so rather than guessing.

## What is deliberately not measured

Whether the content is *correct*. A judge model is not a subject-matter expert on SAP Web
Dispatcher, and pretending otherwise would give a number that feels like accuracy and is not.
That check is you, reading your own daily issues — which is why step 1 exists before anything
else does.
