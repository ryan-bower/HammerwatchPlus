# chatlinks

Item links in chat.

- The base game already links items: **hold the context key (~1 s) on an
  inventory item** (`Character.as MenuContextUp`), which sends the serialized
  item to everyone and raises `GameEvents::PlayerLinkedItem` on each machine.
  Vanilla only shows it in the fading loot log.
- Issue #62, easier to find:
  - **Right-click** any item on the character screen, in the bag or worn. The
    button is read raw (`Platform::IsKeyDown` on what `mouse_right` resolves
    to) and only while the character tab is on top, so in play it stays the
    off-hand attack.
  - A **"[L] Link in chat"** hint on every bag item (hwplib `ItemActions`):
    click it or press L. The key can be rebound on the HammerwatchPlus tab
    (`chatlinks.key`, per machine).
- `HWPChatLinksModule` implements `IEventPlayerLinkedItem` and adds a
  persistent chat line, `<player>: [Item Name]`, with the name in rarity colour
  and the player in player colour. It has no slot or item level any more.
- **Linked items panel** (`HWPChatLinksHUD`, `gui/hwp_chatlinks.gui`): the chat
  box runs in the main menu's script context (`MainMenuGameMode.m_wChat`),
  which gameplay scripts can't reach. A line can only be added (the `AddChat`
  system message), never read back or hovered. So the last 5 links also show
  in a small HUD panel just above the chat (it follows `ui_chat_pos`,
  `ui_chat_width` and `ui_chat_scale`), each in rarity colour.
  - It stays up 30 s after a link, longer while hovered.
  - Hovering a link puts up the item's vanilla tooltip (`Item::BuildItemTooltip`:
    picture, stats, skill, description) beside the line.
  - A remote link carries the whole item (`Item::SaveItem`), so everyone sees
    the same tooltip.
- `hwp link [main|off|head|chest|feet|hands|back]` links an equipped item
  (default main hand) using the same two calls the inventory makes.
- `hwp links` shows the panel again.
- `hwp chatlinks [rclick]`: the status (links, panel and line rects, hover,
  tooltip); `rclick` arms one stand-in right-click for GameLab, which can't
  press the mouse in lab mode.

## Settings

On the HammerwatchPlus tab of the player menu (Quality of Life > Chat item links), per player:

- `chatlinks.enabled` (on): when off, linked items get no chat line or panel on
  your screen (the vanilla loot-log flash stays), the hint and right-click do
  nothing, and `hwp link` says it is off. Takes effect at once.
- `chatlinks.key` (L): the Link in chat key.

Not done: typing `[item]` tokens into the chat input.

## Test checklist

1. `python -m gamelab run fix-chat-links --mode lab`: the hint, its click, the
   L key, the right-click path, the panel, its hover tooltip, and following
   `ui_chat_pos`.
2. Solo: right-click your main hand in the character screen: the chat line and
   the panel show it; hover it on the panel for the tooltip.
3. `hwp link` and `hwp link off` link the equipped items; an empty slot prints
   the "nothing equipped" hint.
4. Co-op: the other player sees the same line with your name in your colour,
   and the same tooltip on their panel.
