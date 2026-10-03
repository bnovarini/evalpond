# Noise: why small gaps mean nothing

Model answers vary, and a small task set is a small sample. Both make a gap look bigger than it is.

## The size of the noise

With n tasks and pass rate p, the standard error is about sqrt(p(1-p)/n). At n = 60 and p = 0.8 that is about 5 points, so a 95% interval is roughly plus or minus 10 points. A 3 point move is well inside it. The report shows the range, not just the point estimate.

We use **Wilson intervals** for pass rates. They behave better than the simple formula near 0% and 100%.

## Comparing two runs

Both runs answered the same tasks, so compare them task by task. Only the tasks whose result **flipped** carry information. We use the exact **McNemar test** on those flips. If one run fixed 6 tasks and broke 6, there is no signal, whatever the pass rates say.

The report words the result as "looks better", "looks worse" or "no clear difference". It never says "better" from a point estimate alone.

## Run-to-run variance

Models can answer differently on the same input, even at temperature 0. Use `evalpond run --repeats 3` to run each task several times. A task that passes in some repeats and fails in others is flagged **unstable**.

## Many comparisons

If you try ten prompts, about one will look significant by luck at the usual cutoff. Say how many things you tried. The report footer reminds you.

## How big a set do you need?

To tell apart a 5 point change reliably you need hundreds of tasks. `stats.min_detectable_gap(n)` gives a rough number. The demo set has 60 tasks. It teaches the mechanics. It cannot support fine decisions.

## The AI grader

AI graders have habits: they can favor long answers, favor their own model's style, or be generous. The report shows how often the AI grader agrees with a human (`evalpond calibrate`, Cohen's kappa) and whether its scores track answer length.
