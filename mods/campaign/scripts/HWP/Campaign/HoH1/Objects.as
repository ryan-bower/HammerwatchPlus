// HoH2 implementations of HoH1's keys, locked chests, locked doors, item drops
// and looping doodad animations, under HoH1-prefixed names (tools/import_hoh1.py
// CLASS_MAP) and HoH1's parameters. HoH1 numbered its keys ("lock" 0-3); HoH2
// names them, so lock N is HoH2's key HOH1_KEYS[N] and the keys show in HoH2's
// HUD (the ace key's name comes from mods/keys when it is on).

const array<string> HOH1_KEYS = { "bronze", "silver", "gold", "ace" };

// "" for an unlocked chest or door (lock -1, or out of range)
string HoH1KeyName(int lock)
{
	if (lock < 0 || lock >= int(HOH1_KEYS.length()))
		return "";
	return HOH1_KEYS[lock];
}

// PlayerRecord.AddKeys stores a temporary the engine's dictionary keeps by
// reference, so the count reads back as garbage (mods/keys KeysModule.as
// SetKeys); a named local survives
void HoH1AddKeys(PlayerRecord@ record, const string &in key, int num)
{
	int stored = max(0, record.GetKeys(key) + num);
	record.keys.set(key, stored);
}

// GiveKey: "amount" keys of "lock" for the player who takes it; the pickup's
// "global" makes every player's machine give its own player one.
class HoH1GiveKey : IEffect, IPlayerEffect
{
	string m_key;
	int m_amount;

	HoH1GiveKey(UnitPtr unit, SValue& params)
	{
		m_key = HoH1KeyName(GetParamInt(unit, params, "lock", false, 0));
		m_amount = GetParamInt(unit, params, "amount", false, 1);
	}

	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }
	void SetWeaponInformation(uint weapon) {}

	void Give(PlayerRecord@ record)
	{
		if (m_key.isEmpty())
			return;
		HoH1AddKeys(record, m_key, m_amount);
		Stats::Add(HashString("key-found-" + m_key), m_amount, record);
		LootLog::PresentPickup(record, Resources::GetString(".item.key." + m_key), m_amount);
	}

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		auto plr = cast<PlayerBase>(target.GetScriptBehavior());
		if (plr is null)
			return false;
		Give(plr.m_record);
		return true;
	}

	bool Apply(PlayerRecord@ instigator, array<PlayerRecord@>@ records, float intensity)
	{
		for (uint i = 0; i < records.length(); i++)
		{
			if (records[i].local)
				Give(records[i]);
		}
		return true;
	}

	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override
	{
		return cast<PlayerBase>(target.GetScriptBehavior()) !is null;
	}
}

// Chest: opens for a key of its "lock" (none at -1) and spawns its HoH1 "loot"
// table (a LootDef, which HoH2 still loads) where it stood.
class HoH1Chest : IUsable
{
	UnitPtr m_unit;
	string m_key;
	LootDef@ m_lootDef;
	SoundEvent@ m_openSnd;

	HoH1Chest(UnitPtr unit, SValue& params)
	{
		m_unit = unit;
		m_key = HoH1KeyName(GetParamInt(unit, params, "lock", false, -1));
		@m_lootDef = LoadLootDef(GetParamString(unit, params, "loot", false));
		@m_openSnd = Resources::GetSoundEvent(GetParamString(unit, params, "open-snd", false));
	}

	void Collide(UnitPtr unit, vec2 pos, vec2 normal, Fixture@ fxSelf, Fixture@ fxOther)
	{
		Player@ player = cast<Player>(unit.GetScriptBehavior());
		if (player !is null && fxSelf.IsSensor())
			player.AddUsable(this);
	}

	void EndCollision(UnitPtr unit, Fixture@ fxSelf, Fixture@ fxOther)
	{
		Player@ player = cast<Player>(unit.GetScriptBehavior());
		if (player !is null && fxSelf.IsSensor())
			player.RemoveUsable(this);
	}

	ITooltip@ GetTooltip() { return null; }
	UnitPtr GetUseUnit() { return m_unit; }
	int UsePriority() { return 0; }
	bool IsInside(UnitPtr unit) { return m_unit.IsColliding(unit); }

	bool CanUse(PlayerBase@ player)
	{
		if (!m_unit.IsValid() || m_unit.IsDestroyed())
			return false;
		if (m_key.isEmpty() || cast<PlayerHusk>(player) !is null)
			return true;
		return player.m_record.GetKeys(m_key) > 0;
	}

	// the opener's machine spends its key; false when it has none
	bool TakeKey(PlayerBase@ player)
	{
		if (m_key.isEmpty() || !player.m_record.local)
			return true;
		if (player.m_record.GetKeys(m_key) <= 0)
			return false;
		HoH1AddKeys(player.m_record, m_key, -1);
		Stats::Add(HashString("chest-unlocked-" + m_key), 1, player.m_record);
		return true;
	}

	void Use(PlayerBase@ player)
	{
		if (m_unit.IsDestroyed() || !m_unit.IsValid() || !TakeKey(player))
			return;

		if (Network::IsServer())
		{
			vec2 pos = xy(m_unit.GetPosition());
			m_unit.Destroy();
			if (m_lootDef !is null)
				m_lootDef.Spawn(pos);
		}

		Stats::Add(HashString("chests-opened"), 1, player.m_record);
		PlaySound3D(m_openSnd, m_unit.GetPosition());
	}

	void NetUse(PlayerHusk@ player) { Use(player); }

	UsableIcon GetIcon(Player@ player)
	{
		if (!CanUse(player))
			return UsableIcon::Cross;
		return m_key.isEmpty() ? UsableIcon::Generic : UsableIcon::Key;
	}
}

// Door: a chest that, instead of breaking open, plays its "open" scene (which
// has no collision) and can't be used again.
class HoH1Door : HoH1Chest
{
	HoH1Door(UnitPtr unit, SValue& params)
	{
		super(unit, params);
	}

	bool CanUse(PlayerBase@ player) override
	{
		if (m_unit.GetCurrentUnitScene().GetName() == "open")
			return false;
		return HoH1Chest::CanUse(player);
	}

	void Use(PlayerBase@ player) override
	{
		if (m_unit.IsDestroyed() || !m_unit.IsValid() || !CanUse(player) || !TakeKey(player))
			return;

		auto plr = cast<Player>(player);
		if (plr !is null)
			plr.RemoveUsable(this);

		m_unit.SetUnitScene("open", true);
		PlaySound3D(m_openSnd, m_unit.GetPosition());
	}

	void NetUse(PlayerHusk@ player) override
	{
		HoH1Chest::NetUse(player);
		auto localPlayer = GetLocalPlayer();
		if (localPlayer !is null)
			localPlayer.RemoveUsable(this);
	}
}

// Item: HoH1's random item of a "quality", a passive pickup. HoH2's are its
// trinkets, so the host drops a random trinket of that quality on the spot
// (anyone may take it, as in HoH1) once the item is shown: a "hidden" one
// waits until a script reveals it.
class HoH1Item
{
	UnitPtr m_unit;
	Item::Quality m_quality;
	bool m_specific;

	HoH1Item(UnitPtr unit, SValue& params)
	{
		m_unit = unit;
		m_quality = Item::ParseQuality(GetParamString(unit, params, "quality", false, "common"));
		if (m_quality == Item::Quality::None)
			m_quality = Item::Quality::Common;
		m_specific = GetParamBool(unit, params, "specific", false, false);
	}

	void Update(int dt)
	{
		if (!Network::IsServer() || m_unit.IsDestroyed() || m_specific)
			return;
		if (m_unit.GetCurrentUnitScene().GetName() == "hidden")
			return;

		auto record = GetLocalPlayerRecord();
		vec3 pos = m_unit.GetPosition();
		m_unit.Destroy();
		if (record !is null)
			Item::DropItem(Item::GetRandomTrinket(record, m_quality), pos, 1, false, null);
	}
}

// StateAnimations: when a scene has played out, the next one from
// "transitions" ({from, to}) starts (the fire turrets' idle -> charge -> fire).
class HoH1StateAnimations
{
	UnitPtr m_unit;
	dictionary m_next;
	string m_currScene;
	int m_currSceneTime;

	HoH1StateAnimations(UnitPtr unit, SValue& params)
	{
		m_unit = unit;
		auto arr = GetParamArray(unit, params, "transitions", false);
		if (arr !is null)
		{
			for (uint i = 0; i < arr.length(); i++)
			{
				string from = GetParamString(unit, arr[i], "from");
				if (!m_next.exists(from))
					m_next.set(from, GetParamString(unit, arr[i], "to"));
			}
		}
		m_currScene = m_unit.GetCurrentUnitScene().GetName();
		m_currSceneTime = m_unit.GetCurrentUnitScene().Length();
	}

	void Update(int dt)
	{
		auto scene = m_unit.GetCurrentUnitScene();
		if (m_currScene != scene.GetName())
		{
			m_currScene = scene.GetName();
			m_currSceneTime = scene.Length();
		}

		m_currSceneTime -= dt;
		if (m_currSceneTime > 0)
			return;

		string next;
		if (!m_next.get(m_currScene, next) || next.isEmpty())
		{
			m_currSceneTime = scene.Length();
			return;
		}
		m_currScene = next;
		m_unit.SetUnitScene(m_currScene, true);
		m_currSceneTime = m_unit.GetCurrentUnitScene().Length();
	}
}
