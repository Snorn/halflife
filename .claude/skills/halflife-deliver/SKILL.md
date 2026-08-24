---
name: halflife-deliver
description: Write every due HalfLife issue unattended — list what is due, follow each brief exactly, record the results, touch nothing else. Built for scheduled sessions; harmless interactively.
---

# HalfLife delivery loop

Write the issues that are due, record them, stop. This runs with nobody
watching, so the boundaries below are the job, not etiquette.

1. Call `halflife_list_due`. Nothing due — say so and stop.
2. For each due subscription, one at a time:
   - Call `halflife_next_brief`.
   - If it reports `needs_compaction: true`, run `halflife_compaction_brief`
     then `halflife_record_compaction` first, and fetch the brief again.
   - Follow the brief's `system_prompt` and `user_prompt` exactly. They carry a
     measured depth rubric and a coverage ledger; do not substitute your own
     judgement about depth, and do not re-explain covered ground.
   - Call `halflife_record_issue`. Report `plan_index` honestly — `0` if the
     issue took a thread or went off-plan. An accurate 0 beats a compliant
     number.
3. Finish with one line per issue written: topic, issue number, title.

## Boundaries

- **Never run extraction** (`halflife_extraction_brief`,
  `halflife_record_signals`). Extraction runs only when the reader asks, and a
  schedule is not the reader asking.
- **Never read or rate** (`halflife_read`, `halflife_feedback`). Those are the
  reader's acts; issues must land in the inbox untouched, because the rating is
  what acknowledges a read.
- **Never subscribe, unsubscribe, pause or change parameters.** Delivery
  writes issues; it does not manage subscriptions.
- If a tool reports the schema is out of date, stop and report the message
  verbatim. Do not run `halflife init` unattended — the reader migrates their
  own database, with a backup.
- A `SeriesComplete` response is a series that finished, not an error. Note it
  and continue with the rest.
