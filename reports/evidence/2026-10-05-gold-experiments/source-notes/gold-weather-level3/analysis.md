# Level 3 stage A: judging conditions against recuse + isolated

Rule fixed before the run: a verdict needs mean d of at least 0.10 either way and a one-sided sign test below 0.0125.

| Condition | Tasks | Best (cond / base) | Mean d | Better / worse | p (better / worse) | Verdict |
|---|---|---|---|---|---|---|
| self | 37 | 0.6216 / 0.7027 | -0.081 | 5 / 11 | 0.962 / 0.105 | no difference |
| shared_trace | 37 | 0.7162 / 0.7027 | +0.013 | 2 / 2 | 0.688 / 0.688 | no difference |
| all | 37 | 0.6757 / 0.7027 | -0.027 | 0 / 2 | 1 / 0.25 | no difference |
| author_label | 37 | 0.7162 / 0.7027 | +0.013 | 2 / 2 | 0.688 / 0.688 | no difference |

## Supporting numbers (reported, not judged)

| Condition | Concordance (pairs) | 1st place by author | grok mean fitness |
|---|---|---|---|
| recuse + isolated | 0.495 (97) | {'gpt': 14, 'opus': 23} | 0.512 |
| self | 0.351 (97) | {'glm': 25, 'gpt': 11, 'opus': 1} | 0.576 |
| shared_trace | 0.515 (97) | {'opus': 29, 'gpt': 8} | 0.527 |
| all | 0.485 (97) | {'opus': 11, 'gpt': 26} | 0.544 |
| author_label | 0.505 (97) | {'opus': 29, 'gpt': 8} | 0.520 |
