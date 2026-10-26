// Dev Arena state across a level change. Script globals do not survive ChangeLevel
// (seed-repeat 20261018-160442, gamelab-hands Hands.as), so Reload floor, a stairway or a
// relaunch would drop the toggles. They ride in the town save, the way GameLab's generation
// seed does: SaveForLevelSwitch saves the town (AGameplayGameMode.as:864-867), the
// TownRecordSave hook (TownRecord.as:380) adds SAVE_KEY, and TownRecordLoad (:446) reads it
// back on the next level, before the modules tick. The engine's cheat flags
// (CVars::Cht*) are script globals too, so they are re-applied from here.
namespace HWP
{
namespace DevArena
{
	const string SAVE_KEY = "hwp-devarena-arena";
	bool g_arenaLoaded;              // this level: the town save carried our state

	void SaveArena(SValueBuilder& b)
	{
		b.PushDictionary(SAVE_KEY);
		b.PushBoolean("god", g_god);
		b.PushBoolean("nocd", g_noCd);
		b.PushBoolean("mana", g_infMana);
		b.PushFloat("speed", g_speed);
		b.PushBoolean("unkillable", g_unkillable);
		b.PushBoolean("passive", g_passive);
		b.PushBoolean("freeze", g_freeze);
		b.PushInteger("brush-kind", g_brushKind);
		b.PushInteger("golem-profile", g_golemProfile);
		b.PushInteger("golem-pool", g_golemPool);
		b.PushInteger("golem-ngp", g_golemNgp);
		b.PushInteger("debuff-every", g_debuffEvery);
		int mask = 0;
		for (uint i = 0; i < g_golemDebuff.length(); i++)
			if (g_golemDebuff[i])
				mask |= 1 << i;
		b.PushInteger("debuffs", mask);
		b.PushString("tab", g_tab);
		b.PushBoolean("dock", g_dockOpen);
		SaveBench(b);
		SaveRelaunch(b);
		SaveTuner(b);
		b.PopDictionary();
	}

	void LoadArena(SValue@ save)
	{
		auto d = save.GetDictionaryEntry(SAVE_KEY);
		if (d is null || d.GetType() != SValueType::Dictionary)
			return;
		UnitPtr u;
		g_god = GetParamBool(u, d, "god", false, false);
		g_noCd = GetParamBool(u, d, "nocd", false, false);
		g_infMana = GetParamBool(u, d, "mana", false, false);
		g_speed = GetParamFloat(u, d, "speed", false, 1.0f);
		g_unkillable = GetParamBool(u, d, "unkillable", false, false);
		g_passive = GetParamBool(u, d, "passive", false, false);
		g_freeze = GetParamBool(u, d, "freeze", false, false);
		g_brushKind = clamp(GetParamInt(u, d, "brush-kind", false, 0), 0, int(ENC_KINDS.length()) - 1);
		g_golemProfile = clamp(GetParamInt(u, d, "golem-profile", false, 3), 0, int(GOLEM_PROFILES.length()) - 1);
		g_golemPool = clamp(GetParamInt(u, d, "golem-pool", false, 1), 0, int(GOLEM_POOLS.length()) - 1);
		g_golemNgp = GetParamInt(u, d, "golem-ngp", false, -1);
		g_debuffEvery = GetParamInt(u, d, "debuff-every", false, 0);
		int mask = GetParamInt(u, d, "debuffs", false, 0);
		for (uint i = 0; i < g_golemDebuff.length(); i++)
			g_golemDebuff[i] = (mask & (1 << i)) != 0;
		string tab = GetParamString(u, d, "tab", false, g_tab);
		if (TABS.find(tab) >= 0)
			g_tab = tab;
		g_dockOpen = GetParamBool(u, d, "dock", false, g_dockOpen);
		LoadBench(d);
		LoadRelaunch(d);
		LoadTuner(d);
		g_arenaLoaded = true;
	}

	// the engine side of the toggles, after a load or a toggle
	void ApplyCheats()
	{
		CVars::ChtGodmode = g_god;
		CVars::ChtNoCooldowns = g_noCd;
		CVars::ChtSpeed = g_speed;
		if (g_infMana)
		{
			SetVar("e_cheats", true);
			SetVar("cht_plr_free_mana_cost", true);
		}
	}
}
}

namespace HWPDevArenaSave
{
	[Hook]
	void TownRecordSave(TownRecord@ town, SValueBuilder& builder)
	{
		HWP::DevArena::SaveArena(builder);
	}

	[Hook]
	void TownRecordLoad(TownRecord@ town, SValue@ save)
	{
		if (save !is null)
			HWP::DevArena::LoadArena(save);
	}
}
