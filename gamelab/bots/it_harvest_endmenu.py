"""Close the mission end window (MissionEndMenu) the town shows after a run with Escape,
as a player does (the window has no close button). The harvest group's IT scenarios
(gamelab/scenarios/it/fishing, it/farming) end runs and then act in town.

  {"do": "bot", "bot": "it_harvest_endmenu", "expect": {"terminal": "done", "topAfter": ""}}

TownGameMode.PostStart opens the window when the run ended Succeeded, Failed or Aborted
(GameModes/TownGameMode.as:28). gui/mission_end.gui has no close button (none in Build
170 either), so a player closes it with Escape: WindowManager.Back pops the top window
when its Back() is true (GUI/WindowManager.as:80, WindowObject.as:302). That path skips
the "close" func's SavePlayerAndTown (GUI/MissionEndMenu.as:752); the town saves itself
on the next level change. The bot waits for the window, lets the reward count-up run
(1.7 s), then posts Escape, retrying while the window stays. Escape is only ever posted
while MissionEndMenu is on top: with no window it opens the pause menu instead.
kwargs: limit (s to wait for the window, 30), tries (3).
Returns terminal ("done", "no_menu", "not_closed"), window (the top window seen),
presses, topAfter.
"""
import time


def top(p):
    return p.state().get("window", "")


def run(p, limit=30, tries=3):
    end, win = time.time() + limit, ""
    while time.time() < end:
        win = top(p)
        if win == "MissionEndMenu":
            break
        time.sleep(0.5)
    if win != "MissionEndMenu":
        return {"terminal": "no_menu", "window": win}
    time.sleep(1.7)
    presses = 0
    for _ in range(tries):
        if top(p) != "MissionEndMenu":
            break
        p.game.key("escape")
        presses += 1
        time.sleep(1.0)
    after = top(p)
    return {"terminal": "done" if after != "MissionEndMenu" else "not_closed", "window": win,
            "presses": presses, "topAfter": after}
