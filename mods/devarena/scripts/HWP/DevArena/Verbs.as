// Dev Arena gl verbs. The arena itself is driven by hotkeys and the dock; these are
// read-only probes for scenarios, plus da-set, the spike's setup path into the same queue
// the dock's Apply uses.
namespace HWP
{
namespace DevArena
{
	// da-skill <skillId> [bind,bind]: read-only. The live skill's rebuilt state: cooldown,
	// the running cooldown, castpoint and timeline times (PlayerSkillDirectional), blocking,
	// anim-length, casts and the gap between the last two cast starts (gameplay ms), and
	// each named bind through PlayerBase.FetchData, the lookup the skill's actions use
	// (PlayerBase.as:265-287). Also pending patches, applies, rebuilds and deferred frames.
	void VerbSkill(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			GameLab::Fail(id, "usage: da-skill <skillId> [bind,bind]");
			return;
		}
		auto plr = LocalPlayer();
		auto s = FindLive(args[0]);
		if (plr is null || s is null)
		{
			GameLab::Fail(id, "no live skill '" + args[0] + "'");
			return;
		}

		auto j = GameLab::Reply(id, true).Str("skill", s.m_id);
		auto def = FindDef(args[0]);
		if (def !is null)
			j.Int("level", plr.m_record.GetSkillLevel(def)).Int("levels", def.m_levelParams.length());

		auto ps = cast<Skills::PlayerSkill>(s);
		if (ps !is null)
		{
			j.Int("cooldown", ps.m_cooldown).Int("cooldownC", ps.m_cooldownC).Int("castingT", ps.m_castingT)
				.Int("animLen", ps.m_animLen).Raw("blocking", "[" + ps.m_blocking.x + "," + ps.m_blocking.y + "]");
		}
		auto act = cast<Skills::ActiveSkill>(s);
		if (act !is null)
			j.Int("cooldown", act.m_cooldown).Int("cooldownC", act.m_cooldownC).Int("castpoint", act.m_castpoint);
		auto dir = cast<Skills::PlayerSkillDirectional>(s);
		if (dir !is null)
		{
			array<string> times;
			for (uint i = 0; i < dir.m_timeline.m_timeline.length(); i++)
				times.insertLast("" + dir.m_timeline.m_timeline[i].time);
			j.Int("castpoint", dir.m_castpoint).Raw("timeline", GameLab::RawArray(times)).Int("skillLen", dir.m_skillLen);
		}

		// the Skill1..3 button this skill answers to, counted the way
		// PlayerTargetingHelper.GetSkillInput does (spells from m_skills[1], passives skipped);
		// -1 for a non-spell
		int slot = -1;
		if (s.m_type == PlayerSkillType::Spell)
		{
			slot = 0;
			for (uint i = 1; i < plr.m_skills.length(); i++)
			{
				if (plr.m_skills[i] is s)
					break;
				if (plr.m_skills[i].GetTargetingMode() != Skills::TargetingMode::Passive
					&& plr.m_skills[i].m_type == PlayerSkillType::Spell)
					slot++;
			}
		}
		array<string> entries;
		for (uint i = 0; i < plr.m_skillsClass.length(); i++)
			if (plr.m_skillsClass[i].m_id == s.m_id)
				entries.insertLast(IsCasting(plr.m_skillsClass[i]) ? "true" : "false");
		j.Int("slot", slot).Raw("classEntries", GameLab::RawArray(entries));

		auto st = Stat(s.m_id);
		j.Int("casts", st.casts).Int("lastGap", st.lastGap).Bool("casting", IsCasting(s));

		if (args.length() > 1)
		{
			auto names = args[1].split(",");
			plr.PrepareSkillFetchData(s.m_skillId);
			array<string> kv;
			for (uint i = 0; i < names.length() && i < 16; i++)
			{
				auto v = plr.FetchData(names[i]);
				kv.insertLast(GameLab::Quote(names[i]) + ":" + (v is null ? "null" : GameLab::Quote(LeafText(v))));
			}
			j.Raw("binds", "{" + join(kv, ",") + "}");
		}

		j.Int("probeBuilt", g_probeBuilt).Int("probeFired", g_probeFired);
		j.Int("pending", Pending() ? 1 : 0).Int("applied", g_applied).Int("rebuilds", g_rebuilds)
			.Int("deferredFrames", g_deferredFrames).Str("lastError", g_lastError);
		GameLab::Emit(j);
	}

	// da-set <skillId> <levelIndex> <path> <value>: setup, a dock cell edit without the dock.
	// Validates and makes a new version (Tuner.as Commit: the first edit fills slot B), then
	// activates it at once unless a skill is casting, in which case the module does on the
	// first frame after the cast ("applied": false here). levelIndex 0 = the base "skill"
	// dict, k = upgrades[k-1].
	void VerbSet(const string &in id, array<string>@ args)
	{
		if (args.length() < 4)
		{
			GameLab::Fail(id, "usage: da-set <skillId> <levelIndex> <path> <value>");
			return;
		}
		string err;
		int v = Commit1(args[0], parseInt(args[1]), args[2], args[3], err);
		if (v < 0)
		{
			GameLab::Fail(id, err);
			return;
		}
		bool casting = AnyCasting();
		bool applied = Flush();
		GameLab::Emit(GameLab::Reply(id, true).Int("version", v).Bool("applied", applied).Bool("casting", casting)
			.Int("pending", Pending() ? 1 : 0));
	}

	// da-freeze <on|off>: spike setup, the Arena tab's freeze toggle without the dock.
	// Freezes every live enemy (m_frozen + the freeze buff, kept up while on) and starts
	// measuring: positions now, the player's hp lost from now.
	void VerbFreeze(const string &in id, array<string>@ args)
	{
		if (args.length() < 1 || (args[0] != "on" && args[0] != "off"))
		{
			GameLab::Fail(id, "usage: da-freeze <on|off>");
			return;
		}
		int n = SetFreeze(args[0] == "on");
		GameLab::Emit(GameLab::Reply(id, true).Bool("freeze", g_freeze).Int("mobs", n));
	}

	// da-buff <path> get | set <param> <value> | give: the buff tab without the dock. get is
	// read-only: the cached def's duration, debuff and modifier count, and the local player's
	// running instance of it (remaining ms, -1 when none). set retunes the def (Buffs.as);
	// give applies a fresh instance to the local player (setup, a cheat).
	void VerbBuff(const string &in id, array<string>@ args)
	{
		if (args.length() < 2 || (args[1] == "set" && args.length() < 4)
			|| (args[1] != "get" && args[1] != "set" && args[1] != "give"))
		{
			GameLab::Fail(id, "usage: da-buff <path> get | set <param> <value> | give");
			return;
		}
		auto def = LoadActorBuff(args[0]);
		if (def is null)
		{
			GameLab::Fail(id, "no buff '" + args[0] + "'");
			return;
		}
		if (args[1] == "set")
		{
			string err;
			if (RetuneBuff(args[0], args[2], args[3], err) is null)
			{
				GameLab::Fail(id, err);
				return;
			}
		}
		bool given = false;
		if (args[1] == "give")
		{
			auto plr = LocalPlayer();
			given = plr !is null && plr.ApplyBuff(ActorBuff(plr, def, 1.0f, false));
		}
		auto live = PlayerBuff(def);
		GameLab::Emit(GameLab::Reply(id, true).Str("buff", args[0]).Int("duration", def.m_duration)
			.Bool("debuff", def.m_debuff).Int("modifiers", def.m_modifiers.length()).Bool("given", given)
			.Int("liveLeft", live is null ? -1 : live.m_duration));
	}

	// da-rng [<seed> <frames>]: with arguments, measurement setup: srand(seed) now and take 8
	// randi(1000) draws `frames` unpaused frames later (Rng.as). Without, read-only: the last
	// probe's seed, delay and draws ("done" false while it waits), and how many probes ran.
	void VerbRng(const string &in id, array<string>@ args)
	{
		if (args.length() == 1 || args.length() > 2)
		{
			GameLab::Fail(id, "usage: da-rng [<seed> <frames>]");
			return;
		}
		if (args.length() == 2)
			StartRng(parseUInt(args[0]), max(0, parseInt(args[1])));
		array<string> draws;
		for (uint i = 0; i < g_rngDraws.length(); i++)
			draws.insertLast("" + g_rngDraws[i]);
		GameLab::Emit(GameLab::Reply(id, true).Int("seed", g_rngSeed).Int("frames", g_rngFrames)
			.Bool("done", g_rngFramesLeft < 0).Raw("draws", GameLab::RawArray(draws)).Int("probes", g_rngProbes));
	}

	// da-compose: read-only. The Compose tab: the slot, its draft text, the CHECK errors, the
	// catalog's projectile/template/snippet counts, the slot's live class and name, the draft on
	// the slot in the wanted version ("" vanilla), the slot's casts, drafts applied (Tuner
	// ApplyOne) and Apply clicks.
	void VerbCompose(const string &in id, array<string>@ args)
	{
		auto d = CmpDraft();
		CmpRecheck();
		array<string> errs;
		for (uint i = 0; i < g_cmpErrs.length(); i++)
			errs.insertLast(GameLab::Quote(g_cmpErrs[i]));
		auto live = FindLive(g_cmpSlot);
		string cls = "";
		if (live !is null)
		{
			auto def = FindDef(g_cmpSlot);
			cls = def is null || def.m_levelParams.length() == 0 ? "" : StrOf(def.m_levelParams[0], "class");
		}
		GameLab::Emit(GameLab::Reply(id, true).Bool("catalog", Catalog() !is null)
			.Int("projectiles", CatIds("projectiles").length()).Int("templates", CatIds("templates").length())
			.Int("snippets", CatIds("snippets").length())
			.Str("slot", g_cmpSlot).Str("draft", d.Text()).Raw("errors", GameLab::RawArray(errs))
			.Str("class", cls).Str("name", live is null ? "" : live.m_name).Str("onSlot", DraftOn(g_cmpSlot))
			.Int("casts", g_cmpSlot == "" ? 0 : Stat(g_cmpSlot).casts).Int("applied", g_composeApplied)
			.Int("clicks", g_cmpApplies).Str("last", g_composeLast));
	}

	// da-dock: read-only. The dock: open, toggles (F1 presses taken), hover (pointer over the
	// open dock), the pointer in UI units, frames drawn and frames it held input focus,
	// clicks taken and the last button, the paused flag of the last module frame, the input
	// focus priority (main.as Focus: 1 gameplay, 2 a menu), and each button's centre in
	// window pixels, for a scenario's pointer (only ids starting with [idPrefix] when given;
	// only what the last frame laid out, so scrolled-off rows are absent), the open tab and
	// the Tune tab's skill. The text field: typing, the field being edited and its text,
	// submits, cancels and text events taken, whether the bindings expect text, the window
	// input lock.
	void VerbDock(const string &in id, array<string>@ args)
	{
		auto r = DockRect();
		float sc = g_gameMode.m_wndScale;
		string prefix = args.length() > 0 ? args[0] : "";
		array<string> px;
		for (uint i = 0; i < g_hits.length() && px.length() < 200; i++)
		{
			if (prefix != "" && g_hits[i].id.findFirst(prefix) != 0)
				continue;
			auto b = g_hits[i].rect;
			px.insertLast(GameLab::Quote(g_hits[i].id) + ":[" + int((b.x + b.z / 2) * sc) + "," + int((b.y + b.w / 2) * sc) + "]");
		}
		GameLab::Emit(GameLab::Reply(id, true).Bool("open", g_dockOpen).Str("tab", g_tab).Int("toggles", g_dockToggles)
			.Bool("hover", g_dockHover).Num("mouseX", g_mouseUi.x).Num("mouseY", g_mouseUi.y)
			.Int("drawn", g_dockDrawn).Int("blocked", g_dockBlocked).Int("clicks", g_dockClicks)
			.Str("lastButton", g_dockLastButton).Bool("paused", g_lastPaused).Int("focus", Focus::g_lastPrio)
			.Int("dockPx", int(r.x * sc)).Int("wndW", g_gameMode.m_wndWidth).Num("scale", sc)
			.Raw("buttons", "{" + join(px, ",") + "}").Int("buttonsTotal", g_hits.length())
			.Str("tab", g_tab).Str("skill", g_tuneSkill).Num("scroll", g_scroll).Str("editing", g_editId)
			.Bool("typing", g_typing).Str("text", g_fieldText.plain()).Int("submits", g_fieldSubmits)
			.Int("cancels", g_fieldCancels).Int("events", g_fieldEvents).Bool("expecting", TextInputBusy())
			.Bool("locked", cast<BaseGameMode>(g_gameMode).m_windowManager.m_lockInput));
	}

	// da-tune [<skillId> <path>]: read-only. The tuner: versions (v0 = vanilla), the wanted and
	// live version, A and B pins, the live slot, pending, curve pins, last action and error,
	// needs-relaunch, versions read from the override file at boot, override lines logged and
	// hotkeys taken. With a skill and a path, that field's curve: the value per level, which
	// levels set it themselves, the fitted growth, the growth step and the masking sub-skills.
	void VerbTune(const string &in id, array<string>@ args)
	{
		if (args.length() == 1 || args.length() > 2)
		{
			GameLab::Fail(id, "usage: da-tune [<skillId> <path>]");
			return;
		}
		EnsureVersions();
		array<string> pins;
		auto keys = g_pins.getKeys();
		keys.sortAsc();
		for (uint i = 0; i < keys.length() && i < 64; i++)
			pins.insertLast(GameLab::Quote(keys[i]));
		auto j = GameLab::Reply(id, true).Int("versions", g_versions.length() - 1).Int("want", g_want)
			.Int("live", g_live).Int("a", g_slotA).Int("b", g_slotB).Str("slot", g_onB ? "B" : "A")
			.Bool("pending", Pending()).Raw("pins", GameLab::RawArray(pins)).Int("pinsTotal", keys.length())
			.Str("lastAction", g_lastAction).Str("lastError", g_lastError).Bool("needsRelaunch", g_needsRelaunch)
			.Int("loaded", g_overrideLoaded).Int("emits", g_overrideEmits).Int("hotkeys", g_hotkeys)
			.Int("edits", g_versions[g_want].edits.length());
		if (args.length() == 2)
		{
			auto def = FindDef(args[0]);
			if (def is null)
			{
				GameLab::Fail(id, "no skill '" + args[0] + "'");
				return;
			}
			auto curve = CurveValues(def, args[1]);
			array<string> vals, owns;
			for (int L = 1; L <= Levels(def); L++)
			{
				bool own;
				auto v = LevelLeaf(def, L, args[1], own);
				vals.insertLast(v is null ? "null" : GameLab::Quote(LeafText(v)));
				owns.insertLast(own ? "true" : "false");
			}
			j.Raw("values", GameLab::RawArray(vals)).Raw("own", GameLab::RawArray(owns))
				.Num("growth", FitGrowth(curve)).Num("step", GrowthStep(def, args[1])).Str("masked", SubMask(def, args[1]));
		}
		GameLab::Emit(j);
	}

	// da-mobs: read-only. Live enemies, how many are frozen, the farthest any mob present at
	// freeze time has moved since (world units), and the player's hp lost since the freeze.
	void VerbMobs(const string &in id, array<string>@ args)
	{
		auto mobs = Mobs();
		int frozen = 0;
		for (uint i = 0; i < mobs.length(); i++)
			if (mobs[i].m_frozen)
				frozen++;
		int tracked;
		float moved = MaxMoved(tracked);
		GameLab::Emit(GameLab::Reply(id, true).Bool("freeze", g_freeze).Int("mobs", mobs.length())
			.Int("frozen", frozen).Int("tracked", tracked).Num("maxMoved", moved).Num("hpLost", g_hpLost));
	}
	// da-loadout: read-only. Presets read at boot, the last one applied and
	// whether the sheet edited it since, queued applies, applies
	// done, how many read back ok and how many did not, the last mismatch, and the record now:
	// class, level, free stars and stat points, equipped base ids by slot and trinket ids.
	void VerbLoadout(const string &in id, array<string>@ args)
	{
		auto plr = LocalPlayer();
		auto j = GameLab::Reply(id, true).Int("presets", g_presetsLoaded).Str("preset", g_preset).Bool("edited", g_sheetEdited)
			.Int("queued", g_presetQueue.length()).Int("applied", g_loadoutApplied).Int("good", g_loadoutOk)
			.Int("bad", g_loadoutBad).Str("lastBad", g_loadoutLastBad);
		if (plr !is null)
		{
			auto rec = plr.m_record;
			array<string> gear, trinkets;
			for (uint i = 0; i < rec.equipped.m_items.length(); i++)
			{
				auto it = cast<Equipment::Item>(rec.equipped.m_items[i]);
				gear.insertLast(it is null ? "null" : GameLab::Quote(it.baseItem.m_id));
			}
			for (uint i = 0; i < rec.trinketInventory.m_items.length() && i < 32; i++)
				trinkets.insertLast(GameLab::Quote(rec.trinketInventory.m_items[i].m_id));
			j.Str("class", rec.playerClass.m_id).Int("level", rec.level).Int("stars", rec.GetFreeSkillPoints())
				.Int("statPoints", rec.GetPlaceableStatPoints()).Raw("gear", GameLab::RawArray(gear))
				.Raw("trinkets", GameLab::RawArray(trinkets)).Int("trinketsTotal", rec.trinketInventory.m_items.length());
		}
		GameLab::Emit(j);
	}

	// da-preset <id|all>: setup. Queue a preset apply (or every preset, in file order) for the
	// next frames with no cast; each apply logs "loadout <id> ok|mismatch ..." (Loadout.as).
	// The same path the Loadout tab's Apply uses.
	void VerbPreset(const string &in id, array<string>@ args)
	{
		if (args.length() != 1)
		{
			GameLab::Fail(id, "usage: da-preset <id|all>");
			return;
		}
		if (!QueuePreset(args[0]))
		{
			GameLab::Fail(id, "no preset '" + args[0] + "'");
			return;
		}
		GameLab::Emit(GameLab::Reply(id, true).Int("queued", g_presetQueue.length()));
	}
}
}

namespace Modules
{
	class HWPDevArenaModule : Module
	{
		HWPDevArenaModule()
		{
			super("devarena");
			GameLab::RegisterVerb("da-skill", "<skillId> [bind,bind]", GameLab::Verb(HWP::DevArena::VerbSkill));
			GameLab::RegisterVerb("da-set", "<skillId> <levelIndex> <path> <value>", GameLab::Verb(HWP::DevArena::VerbSet));
			GameLab::RegisterVerb("da-freeze", "<on|off>", GameLab::Verb(HWP::DevArena::VerbFreeze));
			GameLab::RegisterVerb("da-mobs", "", GameLab::Verb(HWP::DevArena::VerbMobs));
			GameLab::RegisterVerb("da-rng", "[<seed> <frames>]", GameLab::Verb(HWP::DevArena::VerbRng));
			GameLab::RegisterVerb("da-dock", "[idPrefix]", GameLab::Verb(HWP::DevArena::VerbDock));
			GameLab::RegisterVerb("da-tune", "[<skillId> <path>]", GameLab::Verb(HWP::DevArena::VerbTune));
			HWP::DevArena::LoadOverrides();
			HWP::DevArena::LoadPresets();
			GameLab::RegisterVerb("da-loadout", "", GameLab::Verb(HWP::DevArena::VerbLoadout));
			GameLab::RegisterVerb("da-preset", "<id|all>", GameLab::Verb(HWP::DevArena::VerbPreset));
			GameLab::RegisterVerb("da-buff", "<path> get | set <param> <value> | give", GameLab::Verb(HWP::DevArena::VerbBuff));
			GameLab::RegisterVerb("da-arena", "", GameLab::Verb(HWP::DevArena::VerbArena));
			GameLab::RegisterVerb("da-bench", "", GameLab::Verb(HWP::DevArena::VerbBench));
			GameLab::RegisterVerb("da-compose", "", GameLab::Verb(HWP::DevArena::VerbCompose));
			GameLab::RegisterVerb("da-ship", "<classId>", GameLab::Verb(HWP::DevArena::VerbShip));
			GameLab::RegisterVerb("da-tierup", "<buildingId>", GameLab::Verb(HWP::DevArena::VerbTierUp));
			GameLab::RegisterVerb("da-propose", "<note...>", GameLab::Verb(HWP::DevArena::VerbPropose));
			GameLab::RegisterVerb("da-res", "[<w>x<h>]", GameLab::Verb(HWP::DevArena::VerbRes));
			GameLab::RegisterVerb("da-inputlog", "<on [reset]|off>", GameLab::Verb(HWP::DevArena::VerbInputLog));
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("devarena", "HWPDevArenaModule.UpdateFrame"))
				return;
			if (m_guardUpdateFrame.Raw())
			{
				GuardedUpdateFrame(ms, gameInput, menuInput, paused);
				m_guardUpdateFrame.Ok();
				return;
			}
			try { GuardedUpdateFrame(ms, gameInput, menuInput, paused); m_guardUpdateFrame.Ok(); }
			catch { m_guardUpdateFrame.Failed(); }
		}

		void GuardedUpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused)
		{
			HWP::DevArena::Tick(ms, paused);
			HWP::DevArena::TickLoadout();
			if (!paused)
				HWP::DevArena::TickFreeze(ms);
			HWP::DevArena::TickRng(paused);
			HWP::DevArena::TickArena(ms, paused);
			HWP::DevArena::TickRelaunch(paused);
			HWP::DevArena::TickGolem(ms, paused);
			HWP::DevArena::TickBench(ms, gameInput, paused);
			HWP::DevArena::TickDock(ms, gameInput, menuInput, paused);
			HWP::DevArena::TickInputLog(ms, gameInput, paused);
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardRenderWidgets;
		void RenderWidgets(PlayerRecord@ player, int idt, SpriteBatch& sb) override
		{
			if (m_guardRenderWidgets.Skip("devarena", "HWPDevArenaModule.RenderWidgets"))
				return;
			if (m_guardRenderWidgets.Raw())
			{
				GuardedRenderWidgets(player, idt, sb);
				m_guardRenderWidgets.Ok();
				return;
			}
			try { GuardedRenderWidgets(player, idt, sb); m_guardRenderWidgets.Ok(); }
			catch { m_guardRenderWidgets.Failed(); }
		}

		void GuardedRenderWidgets(PlayerRecord@ player, int idt, SpriteBatch& sb)
		{
			HWP::DevArena::RenderDock(sb);
			HWP::DevArena::RenderInputBanner(sb);
		}
	}
}
