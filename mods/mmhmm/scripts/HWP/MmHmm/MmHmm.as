// "Mm-hmm!": a bonus modifier on some rare and epic head items (tweak/hwp/modifiers_mmhmm.sval):
// every crit of its wearer plays a village merchant's voice for everyone, no cooldown. It
// never takes one of the item's rolled modifier slots: the generator has no hook, so the
// local character's hats (worn and in the bag) are checked twice a second and a qualifying
// one gets it added on top. Which hats qualify is a pure function of the item (its base
// item, level, quality and rolled modifiers), so a hat never flips and every machine
// agrees: CHANCE percent of rare and epic hats. A dropped or shop hat shows it once it is
// yours. Legendary items keep no modifiers at all (Item.Finalize), so they never have it.
// The wearer's other moments (revives, wells, secret rooms, trinket sets, last orbs, Ace
// chests: Moments.as, Corpse.as) go through the host as `mmhmm.say` so every peer hears them.
// `hwp mmhmm` lists the worn hat; `hwp mmhmm give` (cheats) adds it to the worn hat.
namespace HWP
{
	namespace MmHmm
	{
		const string MOD_ID = "hwp_mod_mmhmm";
		const int CHANCE = 25; // percent of rare and epic hats
		const int CHECK_MS = 500;
		const string SOUND = "event:/sfx/actors/npcs/male_8/interact_male_8"; // the Material Trader
		const string SAY = "mmhmm.say"; // owner -> host: { why, key }; host -> every peer: { why }
		const int DEDUPE_MS = 1500; // one voice when two machines report the same moment (a revive)

		int g_checkMs = 0;
		int g_added = 0;
		int g_crits = 0; // this machine's crits while wearing it (what `hwp mmhmm` reports)
		int g_said = 0; // voices this machine played for the non-crit moments
		dictionary g_lastKey; // host: key -> time of its last voice

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
			SValueBuilder b;
			b.PushDictionary();
			b.PushString("why", why);
			b.PushString("key", key.isEmpty() ? why + ":" + Lobby::GetLocalPeer() : key);
			b.PopDictionary();
			HWP::Net::Request(SAY, b.Build());
		}

		void OnSayRequest(uint8 peer, SValue@ data)
		{
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
			b.PopDictionary();
			HWP::Net::Broadcast(SAY, b.Build());
		}

		void OnSay(SValue@ data)
		{
			string why = HWP::SV::Str(data, "why");
			PlaySound2D(Resources::GetSoundEvent(SOUND));
			g_said++;
			HWP::Log("mmhmm", "voice: " + why);
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

		// rare or epic, a head item, and in the lucky CHANCE percent
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
			return HashString(key) % 100 < uint(CHANCE);
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
			if (args.length() >= 1 && args[0] == "give")
			{
				if (!HWP::Cheats::On())
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
				+ ", added " + g_added + ", crits with it " + g_crits + ", moments " + g_said + " this session; " + CHANCE + "% of rare and epic hats");
		}
	}
}

namespace HWPMmHmm
{
	// counts only; the voice is the modifier's own crit trigger (modifiers_mmhmm.sval)
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
	class HWPMmHmmModule : Module
	{
		HWPMmHmmModule()
		{
			super("hwp-mmhmm");
			HWP::Net::OnRequest(HWP::MmHmm::SAY, HWP::Net::RequestHandler(HWP::MmHmm::OnSayRequest));
			HWP::Net::OnEvent(HWP::MmHmm::SAY, HWP::Net::EventHandler(HWP::MmHmm::OnSay));
			HWP::Commands::Register("mmhmm", " the worn hat's Mm-hmm! bonus; 'give' (cheats) adds it to the worn hat", HWP::Commands::Handler(HWP::MmHmm::CmdMmHmm));
			if (HWP::MmHmm::Mod() is null)
				HWP::LogError("mmhmm", "no item modifier " + HWP::MmHmm::MOD_ID + " (tweak/hwp/modifiers_mmhmm.sval)");
			HWP::Log("mmhmm", "ready");
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
