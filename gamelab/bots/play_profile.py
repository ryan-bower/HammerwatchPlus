"""Prepare a roster using native creation, XP and saves; never writes real saves."""
import time


def run(pilot, characters, starting_gold=0):
    game = pilot.game
    rows = []
    for index, character in enumerate(characters):
        if index:
            reply = game.gl_cmd("char", character["class_id"], character["name"])
            if not reply.get("ok"):
                return {"ok": False, "rows": rows, "error": reply}
            end = time.monotonic() + 60
            while time.monotonic() < end:
                state = game.gl_cmd("state")
                player = state.get("player", {})
                if state.get("phase") == "town" and player.get("name") == character["name"]:
                    break
                time.sleep(0.25)
            if character["level"] > 1:
                reply = game.gl_cmd("levelup", character["level"] - 1)
                if not reply.get("ok") or reply.get("level") != character["level"]:
                    return {"ok": False, "rows": rows, "error": reply}
        state = game.gl_cmd("state")
        player = state.get("player", {})
        matches = (state.get("phase") == "town" and player.get("class") == character["class_id"]
                   and player.get("name") == character["name"] and player.get("level") == character["level"]
                   and not player.get("dead"))
        saved = game.gl_cmd("save")
        rows.append({"requested": character, "player": player, "ok": matches and saved.get("ok", False)})
        if not rows[-1]["ok"]:
            return {"ok": False, "rows": rows}
    balance = game.gl_cmd("townmoney")
    saved = game.gl_cmd("save")
    return {"ok": balance.get("ok", False) and balance.get("gold") == starting_gold and saved.get("ok", False),
            "rows": rows, "starting_gold": starting_gold, "observed_gold": balance.get("gold")}
