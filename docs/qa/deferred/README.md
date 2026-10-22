# Deferred QA source: portable recovery

The committed [2026-10-22 bundle](2026-10-22-unapplied.json) preserves all 49 UTF-8
files from the old local recovery ZIP: plans, drafts, manifests, diffs, controls and
designs. Every entry records its original path, byte count, SHA256 and `content`
string. Encoding that string as UTF-8 recovers exact original bytes, including line
endings. The [index](../../generated/qa_deferred_work.json) records bundle/origin
hashes. A fresh clone can inspect these sources without the original workspace.

**Status: UNAPPLIED / NATIVE UNTESTED.** Preservation does not install a fix or prove
a passing test. These source drafts are outside runtime and release inputs.

## Inspect a draft

Run this Python in a shell/REPL from the repository root. It reads source without
installing it:

```python
import hashlib
import json
from pathlib import Path

bundle = json.loads(Path("docs/qa/deferred/2026-10-22-unapplied.json").read_text())
assert len(bundle["files"]) == bundle["file_count"]
for item in bundle["files"]:
    raw = item["content"].encode("utf-8")
    assert len(raw) == item["bytes"]
    assert hashlib.sha256(raw).hexdigest() == item["sha256"]
    print(item["original_path"], item["sha256"])

selected = next(item for item in bundle["files"]
                if item["original_path"].endswith("/qa_native_return.py.pending"))
print(selected["content"])
```

## Resume selected work

1. Read the [checkpoint](../../generated/qa_pr_checkpoint.json) and
   [known failures](../REGRESSIONS.md); pick one bounded problem.
2. Inspect its manifest, draft and failing measurement. Historical results paths
   and absolute paths inside payloads refer to the old workspace. Resolve source
   drafts by `original_path` in this bundle. Raw logs remain local and may be
   unavailable in a fresh clone.
3. Compare the draft with current committed source and the pinned game build.
   Rebase the selected change into a fresh reviewed plan. Do not execute the
   archived installer: its HEAD/worktree pins and local paths predate the PR.
   Do not bypass hash checks or copy all payloads into live source.
4. Apply only the reviewed selection at a drained native queue boundary, then run
   compile/load and actual consumer/control checks before awarding credit. Keep
   the original failure and the new source epoch in the handoff.

O-v2 reviewed 21 files. Other bundle entries are supporting or additional deferred
work; 49 preserved files do not mean 49 ready changes. The damage observer lacks a
native two-skill contract; the own-active design has not proven ordinary lifecycles.
