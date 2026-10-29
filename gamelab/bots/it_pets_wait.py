"""Integration tests, pets group: wait for something the game does on its own time, by
polling one gl verb until its reply matches, so a scenario need not guess a `sleep`.

  {"do": "bot", "bot": "it_pets_wait",
   "kwargs": {"verb": "near", "args": [9999, "pet_bowl"], "expect": {"count": 1}, "timeout": 20},
   "expect": {"terminal": "done"}}

kwargs:
- cinema (default True): first wait until the town arrival cinematic is over (`gl cinema`
  active false; while it runs the game walks the player itself and drops input,
  Player.as:1388-1395, brief "Town arrival cinematic").
- verb, args, expect: poll `verb args` every `every` seconds (0.5) until the reply matches
  `expect` (the runner's own `check`: literals, between, match, not, in). No verb: only the
  cinema wait.
- timeout (s, default 30).
Returns terminal ("done", "timeout", "cinematic"), reply (the last reply), waited (s),
polls, mismatch (the last mismatch list).
"""
import time

from gamelab.runner import check


def run(p, verb=None, args=(), expect=None, timeout=30, every=0.5, cinema=True):
    start = time.time()
    end = start + timeout
    c = {}
    if cinema:
        while time.time() < end:
            c = p.cmd("cinema")
            if not c.get("active"):
                break
            time.sleep(0.5)
        if c.get("active"):
            return {"terminal": "cinematic", "reply": c, "waited": round(time.time() - start, 2), "polls": 0,
                    "mismatch": ["a cinematic still runs"]}
    if not verb:
        return {"terminal": "done", "reply": c, "waited": round(time.time() - start, 2), "polls": 0, "mismatch": []}
    polls, reply, bad = 0, {}, ["never polled"]
    while True:
        reply = p.cmd(verb, *args)
        polls += 1
        bad = check(reply, expect or {})
        if not bad:
            return {"terminal": "done", "reply": reply, "waited": round(time.time() - start, 2), "polls": polls,
                    "mismatch": []}
        if time.time() >= end:
            break
        time.sleep(every)
    return {"terminal": "timeout", "reply": reply, "waited": round(time.time() - start, 2), "polls": polls,
            "mismatch": bad}
