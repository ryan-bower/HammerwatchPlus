// "Mm-hmm!": a bonus modifier on some rare and epic head items (tweak/hwp/modifiers_mmhmm.sval):
// every crit of its wearer plays a village woman's "mm-hmm!" from the wearer's body. A voice
// plays to the end before the same wearer says it again (Voice: crits closer together than
// VOICE_MS are held back, issue #31). It
// never takes one of the item's rolled modifier slots: the generator has no hook, so the
// local character's hats (worn and in the bag) are checked twice a second and a qualifying
// one gets it added on top. Which hats qualify is a pure function of the item (its base
// item, level, quality and rolled modifiers), so a hat never flips and every machine
// agrees: mmhmm.chance (25) percent of rare and epic hats. A dropped or shop hat shows it once it is
// yours. Legendary items keep no modifiers at all (Item.Finalize), so they never have it.
// The wearer's other moments (revives, wells, secret rooms, trinket sets, last orbs, Ace
// chests: Moments.as, Corpse.as) go through the host as `mmhmm.say` so every peer hears them,
// from that wearer. `hwp mmhmm` lists the worn hat; `hwp mmhmm give` (cheats) adds it to the
// worn hat; `hwp mmhmm voice [n]` (cheats) says it n times at once (one plays).
namespace HWP
{
	namespace MmHmm
	{
		const string MOD_ID = "hwp_mod_mmhmm";
		const int CHECK_MS = 500;
		// the village's Equipment Buyer, Enchanter and Mystic (female_2): two takes of "mm-hmm!",
		// 0.28 and 0.37 s; it was the Material Trader's (male_8) before issue #31
		const string SOUND = "event:/sfx/actors/npcs/female_2/interact_female_2";
		const string SAY = "mmhmm.say"; // owner -> host: { why, key }; host -> every peer: { why, peer }
		const int DEDUPE_MS = 1500; // one voice when two machines report the same moment (a revive)
		// a wearer's next voice waits this long after the last, so each one plays to the end
		// (the longer take is 0.37 s; SoundInstance cannot tell when an event has stopped)
		const int VOICE_MS = 500;

		int g_checkMs = 0;
		int g_added = 0;
		int g_crits = 0; // this machine's crits while wearing it (what `hwp mmhmm` reports)
		int g_said = 0; // non-crit moments this machine was told to voice
		int g_voiced = 0; // voices this machine played (crits and moments)
		int g_held = 0; // voices held back because the wearer's last one was still playing
		dictionary g_lastKey; // host: key -> time of its last voice
		dictionary g_voiceUntil; // unit id -> scene time its voice ends

		// The wearer says it, from their body (3D, following the unit), unless their last
		// voice is still playing. Every machine runs this for every wearer: the crit
		// trigger is net-synced and the moments are broadcast.
		bool Voice(UnitPtr who, const string &in why)
		{
			if (!g_enabled || !who.IsValid())
				return false;
			int now = g_scene.GetTime();
			string id = "" + who.GetId();
			int until;
			if (g_voiceUntil.get(id, until) && now < until)
			{
				g_held++;
				return false;
			}
			auto snd = Resources::GetSoundEvent(SOUND);
			if (snd is null)
			{
				HWP::LogError("mmhmm", "no sound " + SOUND);
				return false;
			}
			g_voiceUntil.set(id, now + VOICE_MS);
			PlaySound3D(snd, who);
			g_voiced++;
			vec3 pos = who.GetPosition();
			HWP::Log("mmhmm", "voice: " + why + " from " + who.GetDebugName() + " at " + int(pos.x) + "," + int(pos.y));
			return true;
		}

		// Settings (host-synced, so every machine agrees). mmhmm.enabled off: no hat gets the
		// bonus, no voice plays (the crit trigger's chance is 0); hats that have it keep it, so
		// turning it back on finds them as they were. mmhmm.chance: percent of rare and epic
		// hats that qualify (a lower value never takes it off a hat). mmhmm.crits: the crit voice.
		bool g_enabled = true;
		bool g_critVoice = true;
		int g_chance = 25;
		vec2 g_critChance = vec2(1, 1); // the crit trigger's chance as loaded (modifiers_mmhmm.sval: 1)

		// the modifier's crit TriggerEffect is one shared definition: a chance of 0 silences it
		// for every hat on this machine
		void ApplyCritVoice()
		{
			auto mod = Mod();
			if (mod is null)
				return;
			for (uint i = 0; i < mod.modifiers.length(); i++)
			{
				auto te = cast<Modifiers::TriggerEffect>(mod.modifiers[i]);
				if (te is null)
					continue;
				if (te.m_chance.x != 0 || te.m_chance.y != 0)
					g_critChance = te.m_chance;
				te.m_chance = (g_enabled && g_critVoice) ? g_critChance : vec2(0, 0);
			}
		}

		void RefreshSettings()
		{
			g_enabled = HWP::Settings::GetBool("mmhmm.enabled", true);
			g_critVoice = HWP::Settings::GetBool("mmhmm.crits", true);
			g_chance = clamp(HWP::Settings::GetInt("mmhmm.chance", 25), 0, 100);
			ApplyCritVoice();
		}

		void OnSettingChanged(const string &in key)
		{
			if (key.findFirst("mmhmm.") == 0)
				RefreshSettings();
		}

		// the local character wears a hat with the bonus
		bool Wearing(PlayerRecord@ rec)
		{
			if (rec is null || rec.equipped is null)
				return false;
			return Has(cast<Equipment::Item>(rec.equipped.m_items[int(EquippedItemsSlots::Head)]));
		}

		// A moment the wearer's machine noticed (a revive, a pool, ...): the host makes every
		// peer play the voice. `key` names the moment, so the same one reported twice (the
		// reviver's and the revived player's machine) plays once.
		void Say(const string &in why, const string &in key = "")
		{
			if (!g_enabled)
				return;
			SValueBuilder b;
			b.PushDictionary();
			b.PushString("why", why);
			b.PushString("key", key.isEmpty() ? why + ":" + Lobby::GetLocalPeer() : key);
			b.PopDictionary();
			HWP::Net::Request(SAY, b.Build());
		}

		void OnSayRequest(uint8 peer, SValue@ data)
		{
			if (!g_enabled)
				return;
			string why = HWP::SV::Str(data, "why");
			string key = HWP::SV::Str(data, "key");
			int now = g_scene.GetTime();
			int last;
			if (g_lastKey.get(key, last) && now - last < DEDUPE_MS)
				return;
			g_lastKey.set(key, now);
			SValueBuilder b;
			b.PushDictionary();
			b.PushString("why", why);
			b.PushInteger("peer", peer);
			b.PopDictionary();
			HWP::Net::Broadcast(SAY, b.Build());
		}

		// the moment's wearer: the player of the machine that reported it
		UnitPtr WearerUnit(int peer)
		{
			auto rec = GetPlayerRecordByPeer(peer);
			if (rec !is null && rec.actor !is null)
				return rec.actor.m_unit;
			return UnitPtr();
		}

		void OnSay(SValue@ data)
		{
			if (!g_enabled)
				return;
			string why = HWP::SV::Str(data, "why");
			int peer = HWP::SV::Int(data, "peer", -1);
			g_said++;
			UnitPtr who = WearerUnit(peer);
			if (!who.IsValid())
			{
				HWP::Log("mmhmm", "voice: " + why + ", no wearer unit (peer " + peer + "), not played");
				return;
			}
			Voice(who, why);
		}

		Equipment::ItemModifier@ Mod()
		{
			return Equipment::ItemModifier::Get(HashString(MOD_ID));
		}

		bool Has(Equipment::Item@ item)
		{
			auto mod = Mod();
			return item !is null && mod !is null && item.mods.findByRef(mod) >= 0;
		}

		// rare or epic, a head item, and in the lucky g_chance percent (mmhmm.chance)
		bool Qualifies(Equipment::Item@ item)
		{
			if (item is null || item.baseItem is null || item.baseItem.slot != Equipment::Slot::Head)
				return false;
			if (item.quality != Item::Quality::Rare && item.quality != Item::Quality::Epic)
				return false;
			string key = item.baseItem.m_id + ":" + int(item.itemLevel) + ":" + int(item.quality);
			for (uint i = 0; i < item.mods.length(); i++)
			{
				if (item.mods[i].m_id != MOD_ID)
					key += ":" + item.mods[i].m_id;
			}
			return HashString(key) % 100 < uint(g_chance);
		}

		bool Add(Equipment::Item@ item)
		{
			auto mod = Mod();
			if (mod is null || item is null || Has(item))
				return false;
			item.mods.insertLast(mod);
			item.Finalize(item.intensity, int(item.itemLevel), int(item.upgradeLevel), item.colorA, item.colorB);
			g_added++;
			HWP::Log("mmhmm", "added to " + item.baseItem.m_id + " (" + item.GetName() + ")");
			return true;
		}

		void Check(PlayerRecord@ rec)
		{
			if (rec is null || rec.equipped is null)
				return;
			bool worn = false;
			auto head = cast<Equipment::Item>(rec.equipped.m_items[int(EquippedItemsSlots::Head)]);
			if (Qualifies(head) && Add(head))
				worn = true;
			if (rec.equipInventory !is null)
			{
				for (uint i = 0; i < rec.equipInventory.m_items.length(); i++)
				{
					auto item = cast<Equipment::Item>(rec.equipInventory.m_items[i]);
					if (Qualifies(item))
						Add(item);
				}
			}
			if (worn)
			{
				// the worn hat's modifiers changed: the crit trigger joins the player's list
				rec.RefreshStats();
				auto plr = cast<PlayerBase>(rec.actor);
				if (plr !is null)
					plr.RefreshModifiers();
			}
		}

		void Update(int ms)
		{
			g_checkMs -= ms;
			if (g_checkMs > 0)
				return;
			g_checkMs = CHECK_MS;
			if (!g_enabled)
			{
				// back on, the first poll only takes the counts again (no voice for what
				// happened while it was off)
				g_seen.seeded = false;
				return;
			}
			auto rec = GetLocalPlayerRecord();
			Check(rec);
			Moments(rec);
		}

		void CmdMmHmm(array<string>@ args)
		{
			auto rec = GetLocalPlayerRecord();
			if (rec is null || rec.equipped is null)
			{
				HWP::Commands::Reply("mmhmm: no character");
				return;
			}
			auto head = cast<Equipment::Item>(rec.equipped.m_items[int(EquippedItemsSlots::Head)]);
			if (args.length() >= 1 && args[0] == "voice")
			{
				if (!HWP::Cheats::On() || rec.actor is null)
					return;
				int n = args.length() >= 2 ? clamp(parseInt(args[1]), 1, 20) : 1;
				int played = 0;
				for (int i = 0; i < n; i++)
				{
					if (Voice(rec.actor.m_unit, "test"))
						played++;
				}
				HWP::Commands::Reply("mmhmm voice: " + played + " of " + n + " played, voices " + g_voiced + ", held back " + g_held);
				return;
			}
			if (args.length() >= 1 && args[0] == "give")
			{
				if (!HWP::Cheats::On() || !g_enabled)
					return;
				if (head is null)
				{
					HWP::Commands::Reply("mmhmm: no hat on");
					return;
				}
				if (Add(head))
				{
					rec.RefreshStats();
					auto plr = cast<PlayerBase>(rec.actor);
					if (plr !is null)
						plr.RefreshModifiers();
				}
			}
			HWP::Commands::Reply("mmhmm: hat " + (head is null ? "none" : head.baseItem.m_id + " (" + head.GetName() + ")")
				+ ", bonus " + (Has(head) ? "yes" : "no") + ", qualifies " + (Qualifies(head) ? "yes" : "no")
				+ ", added " + g_added + ", crits with it " + g_crits + ", moments " + g_said + ", voices " + g_voiced + ", held back " + g_held + " this session; " + g_chance + "% of rare and epic hats" + (g_enabled ? "" : " (off: mmhmm.enabled)"));
		}
	}
}

// The crit trigger's effect (modifiers_mmhmm.sval): the wearer says it through Voice, so a
// burst of crits does not cut the last voice short. The TriggerEffect is net-synced, so every
// machine runs it with the wearer (or their husk) as owner.
class HWPMmHmmVoice : IEffect
{
	HWPMmHmmVoice(UnitPtr unit, SValue& params) {}

	void SetWeaponInformation(uint weapon) {}
	CanEvade IsEvadable(Actor@ attacker) { return CanEvade::Neither; }

	bool Apply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity, bool husk)
	{
		if (!CanApply(owner, target, pos, dir, intensity))
			return false;
		HWP::MmHmm::Voice(owner !is null ? owner.m_unit : target, "crit");
		return true;
	}

	bool CanApply(Actor@ owner, UnitPtr target, vec2 pos, vec2 dir, float intensity) override
	{
		return intensity > 0 && ((owner !is null && owner.m_unit.IsValid()) || target.IsValid());
	}
}

namespace HWPMmHmm
{
	// counts only; the voice is the modifier's crit trigger (HWPMmHmmVoice)
	[Hook]
	void PlayerDamagedActor(Player@ player, Actor@ actor, DamageInfo@ di)
	{
		if (di is null || di.Crit <= 0 || player is null || player.m_record is null || player.m_record.equipped is null)
			return;
		if (HWP::MmHmm::Has(cast<Equipment::Item>(player.m_record.equipped.m_items[int(EquippedItemsSlots::Head)])))
			HWP::MmHmm::g_crits++;
	}
}

namespace Modules
{
	class HWPMmHmmModule : Module, HWP::ModuleStart
	{
		HWPMmHmmModule()
		{
			super("hwp-mmhmm");
			HWP::Net::OnRequest(HWP::MmHmm::SAY, HWP::Net::RequestHandler(HWP::MmHmm::OnSayRequest));
			HWP::Net::OnEvent(HWP::MmHmm::SAY, HWP::Net::EventHandler(HWP::MmHmm::OnSay));
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::MmHmm::OnSettingChanged));
			HWP::Commands::Register("mmhmm", " the worn hat's Mm-hmm! bonus; 'give' (cheats) adds it to the worn hat; 'voice [n]' (cheats) says it n times at once", HWP::Commands::Handler(HWP::MmHmm::CmdMmHmm));
			if (HWP::MmHmm::Mod() is null)
				HWP::LogError("mmhmm", "no item modifier " + HWP::MmHmm::MOD_ID + " (tweak/hwp/modifiers_mmhmm.sval)");
			HWP::Log("mmhmm", "ready");
		}

		void Start(StartMode sMode)
		{
			HWP::MmHmm::RefreshSettings();
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("mmhmm", "HWPMmHmmModule.UpdateFrame"))
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
			HWP::MmHmm::Update(ms);
		}
	}
}
