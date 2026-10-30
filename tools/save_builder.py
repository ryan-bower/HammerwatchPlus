"""Small desktop roster editor for tools/run.py; importing it never opens a window."""
from __future__ import annotations

from dataclasses import dataclass, field

CLASSES = {
    "warrior": "Warrior", "paladin": "Paladin", "ranger": "Ranger", "rogue": "Rogue",
    "wizard": "Wizard", "sorcerer": "Sorcerer", "warlock": "Warlock", "priest": "Priest",
    "hwp_firearms": "Firearms Specialist", "hwp_thief": "Thief",
    "hwp_gladiator": "Gladiator", "hwp_witchhunter": "Witch Hunter",
}
MAX_CHARACTERS = 16
MAX_LEVEL = 20  # NG0's native cap; the builder does not silently grant NG+ progress.
DEFAULT_GOLD = 1_000_000
MAX_GOLD = 2_147_483_647  # Native material balances are signed 32-bit integers.


def parse_gold(value: str) -> int:
    try:
        gold = int(value.replace(",", "").strip())
    except ValueError:
        raise ValueError("Starting gold must be a whole number") from None
    if not 0 <= gold <= MAX_GOLD:
        raise ValueError(f"Starting gold must be between 0 and {MAX_GOLD:,}")
    return gold


@dataclass(frozen=True)
class Character:
    class_id: str
    level: int
    name: str

    def validate(self, available: dict[str, str] | None = None) -> None:
        if self.class_id not in (available if available is not None else CLASSES):
            raise ValueError(f"Class {self.class_id!r} is not available in the selected packages")
        if type(self.level) is not int or not 1 <= self.level <= MAX_LEVEL:
            raise ValueError(f"Character level must be between 1 and {MAX_LEVEL}")
        if not self.name.strip() or len(self.name.encode("utf-8")) > 48:
            raise ValueError("Character names must contain 1-48 UTF-8 bytes")
        # Names are passed as one token to GameLab's existing char verb.
        if any(c.isspace() or c in '\"\'\\+|' or ord(c) < 32 for c in self.name):
            raise ValueError("Use a character name without spaces, quotes, backslashes, + or |")


@dataclass
class Plan:
    profile_name: str | None = None
    characters: list[Character] = field(default_factory=list)
    starting_gold: int = DEFAULT_GOLD

    def validate(self, available: dict[str, str] | None = None) -> None:
        if type(self.starting_gold) is not int or not 0 <= self.starting_gold <= MAX_GOLD:
            raise ValueError(f"Starting gold must be a whole number between 0 and {MAX_GOLD:,}")
        if len(self.characters) > MAX_CHARACTERS:
            raise ValueError(f"Add at most {MAX_CHARACTERS} characters")
        if self.profile_name is not None and (not self.profile_name.strip()
                or len(self.profile_name.encode("utf-8")) > 240 or "\0" in self.profile_name):
            raise ValueError("Profile names must contain 1-240 UTF-8 bytes without NUL")
        for character in self.characters:
            character.validate(available)
        names = [c.name.casefold() for c in self.characters]
        if len(names) != len(set(names)):
            raise ValueError("Give each character a different name")


def parse_character(value: str) -> Character:
    parts = value.split(":", 2)
    if len(parts) < 2:
        raise ValueError("Use --character CLASS:LEVEL[:NAME], for example sorcerer:15:TestSorc")
    class_id = {"sorc": "sorcerer", "firearms": "hwp_firearms", "thief": "hwp_thief",
                "gladiator": "hwp_gladiator", "witchhunter": "hwp_witchhunter"}.get(parts[0], parts[0])
    character = Character(class_id, int(parts[1]), parts[2] if len(parts) > 2 else f"{class_id.removeprefix('hwp_').title()}{parts[1]}")
    character.validate()
    return character


def show(plan: Plan, available: dict[str, str]) -> Plan | None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("HammerwatchPlus · Save builder")
    root.geometry("720x665")
    root.minsize(680, 625)
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"))
    style.configure("Treeview", rowheight=30)
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Build your test save", style="Title.TLabel").pack(anchor="w")
    ttk.Label(frame, text="A new profile with the latest local mods. Your existing profiles stay available.",
              wraplength=650).pack(anchor="w", pady=(6, 18))
    profile = tk.StringVar(value=plan.profile_name or "")
    ttk.Label(frame, text="Profile name  (optional)").pack(anchor="w")
    ttk.Entry(frame, textvariable=profile).pack(fill="x", pady=(4, 16))
    gold = tk.StringVar(value=f"{plan.starting_gold:,}")
    ttk.Label(frame, text="Starting gold  (shared by this profile)").pack(anchor="w")
    ttk.Entry(frame, textvariable=gold).pack(fill="x", pady=(4, 16))
    form = ttk.Frame(frame)
    form.pack(fill="x")
    name = tk.StringVar(value="TestSorc")
    selected = tk.StringVar(value=available.get("sorcerer", next(iter(available.values()))))
    level = tk.StringVar(value="15")
    for col, title in enumerate(("Character name", "Class", "Level")):
        ttk.Label(form, text=title).grid(row=0, column=col, sticky="w", pady=(0, 4))
    ttk.Entry(form, textvariable=name, width=23).grid(row=1, column=0, sticky="ew", padx=(0, 10))
    ttk.Combobox(form, textvariable=selected, values=list(available.values()), state="readonly", width=22).grid(row=1, column=1, sticky="ew", padx=(0, 10))
    ttk.Spinbox(form, from_=1, to=MAX_LEVEL, textvariable=level, width=5).grid(row=1, column=2)
    form.columnconfigure(0, weight=1)
    form.columnconfigure(1, weight=1)
    rows = list(plan.characters)
    tree = ttk.Treeview(frame, columns=("name", "class", "level"), show="headings", height=7)
    for column, heading, width in (("name", "Character", 230), ("class", "Class", 230), ("level", "Level", 65)):
        tree.heading(column, text=heading)
        tree.column(column, width=width, anchor="w")

    def refresh():
        tree.delete(*tree.get_children())
        for i, character in enumerate(rows):
            tree.insert("", "end", iid=str(i), values=(character.name, available[character.class_id], character.level))

    def add():
        try:
            by_label = {label: key for key, label in available.items()}
            character = Character(by_label[selected.get()], int(level.get()), name.get().strip())
            Plan(profile.get().strip() or None, rows + [character], parse_gold(gold.get())).validate(available)
            rows.append(character)
            refresh()
        except (ValueError, KeyError) as error:
            messagebox.showerror("Check character", str(error), parent=root)

    def remove():
        for index in sorted((int(i) for i in tree.selection()), reverse=True):
            rows.pop(index)
        refresh()

    actions = ttk.Frame(frame)
    actions.pack(fill="x", pady=10)
    ttk.Button(actions, text="Add character", command=add).pack(side="left")
    ttk.Button(actions, text="Remove selected", command=remove).pack(side="left", padx=8)
    tree.pack(fill="both", expand=True)
    refresh()
    ttk.Label(frame, text="Levels 1–20 · Normal starting gear · Earned skill and attribute points stay unspent\n"
              "Preparing characters runs the game privately first and can take a few minutes.",
              wraplength=650).pack(anchor="w", pady=(14, 18))
    result = None

    def finish(empty=False):
        nonlocal result
        try:
            candidate = Plan(profile.get().strip() or None, [] if empty else list(rows), parse_gold(gold.get()))
            candidate.validate(available)
            if not empty and not rows:
                raise ValueError("Add a character first, or choose No preset characters")
        except ValueError as error:
            messagebox.showerror("Check save", str(error), parent=root)
            return
        result = candidate
        root.destroy()

    footer = ttk.Frame(frame)
    footer.pack(fill="x")
    ttk.Button(footer, text="Cancel", command=root.destroy).pack(side="left")
    ttk.Button(footer, text="Build save & launch", command=finish).pack(side="right")
    ttk.Button(footer, text="No preset characters", command=lambda: finish(True)).pack(side="right", padx=10)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    return result
