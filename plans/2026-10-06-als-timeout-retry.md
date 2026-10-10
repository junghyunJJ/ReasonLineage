# ALS request-time retry

User explicitly requested increasing time and retrying. Use existing isolated worktree and protocol0.4. Run onlyALS/reasonlineage, preserving all prior outcomes and the three completed ALS solo baselines. Request ceiling2700s, local45m/800000reportedtokens/40admissions; normal30calls. Two held-outALS forward/reverse ratings on a completed retry plus prior controls; total60m/42admissions. NoOpus, no extra generation slots. A new clock applies only to this newly authorized retry; old clocks remain immutable.

Task1: Prepare a small standalone execution helper using existing pilot APIs. Verify zero calls when endpoint preflight fails, exact32calls on healthy fake services, unchanged baselines, and no evaluation after generation failure. No changes to corealgorithm or existing protocol.
Task2: Run the helper in a fresh output folder. Current execution environment has restricted network and read-onlyGit metadata. If connectivity fails, write a preflight-only blocked record with0modelcalls and stop; do not manufacture hypothesis failures or bypass permissions. Actual model generation/evaluation remains unfinished until connectivity is available.
