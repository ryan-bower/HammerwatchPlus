// The native clip remains one shared ammunition pool. Extended Clip Crit, however,
// counts each gun's own magazine (the planner's dual-pistol example), including
// unequal pistol/cannon firing. These counters affect bonuses only: they never
// add/remove native rounds, gate a shot, start a reload or change a timeline.
namespace HWP
{
	namespace Firearms
	{
		string MagazineItemId(PlayerRecord@ rec, bool off)
		{
			if (rec is null || rec.equipped is null)
				return "";
			auto item = cast<Equipment::Item>(rec.equipped.m_items[off ? EquippedItemsSlots::OffHand : EquippedItemsSlots::MainHand]);
			return item is null || item.baseItem is null ? "" : item.baseItem.m_id;
		}

		int BaseMagazine(const string &in id)
		{
			if (id.findFirst("hwp_glock_") == 0)
				return 10;
			if (id.findFirst("hwp_hcannon_") == 0)
				return 6;
			if (id.findFirst("hwp_rifle_") == 0 || id.findFirst("hwp_flamerifle_") == 0 || id.findFirst("hwp_autorifle_") == 0)
				return 30;
			return 0;
		}

		class MagazineState
		{
			Guid m_id;
			uint m_uniqueKey;
			PlayerBase@ m_actor;
			string m_mainId, m_offId;
			int m_mainMax, m_offMax;
			int m_main, m_off;
			int m_observed, m_pending;
			bool m_initialized, m_restorePending;
			int m_savedMain = -1, m_savedOff = -1;
			string m_savedMainId, m_savedOffId;

			MagazineState(PlayerRecord@ rec) { m_id = rec.id; m_uniqueKey = rec.uniqueKey; }

			// Use core's existing optional hwp bag: no native save fields, stack
			// definitions or serialization hooks change. Its record-owned data survives
			// scene replacement, saves and network join. Old saves need no migration.
			bool RestoreStored(PlayerBase@ plr, int raw)
			{
				auto bag = HWP::SaveData::Player(plr.m_record);
				if (bag.GetString("firearms.mag.main-id") != m_mainId || bag.GetString("firearms.mag.off-id") != m_offId)
					return false;
				int main = bag.GetInt("firearms.mag.main", -1), off = bag.GetInt("firearms.mag.off", -1);
				int total = bag.GetInt("firearms.mag.total", -1);
				if (main < 0 || off < 0 || main > 100000 || off > 100000 || main + off != total)
					return false;
				m_main = main;
				m_off = off;
				m_restorePending = raw == 0 && total > 0;
				if (!m_restorePending)
					SetTotal(raw); // native ammunition is authoritative, including town refills
				return true;
			}

			void Persist(PlayerBase@ plr)
			{
				if (m_restorePending || (m_main == m_savedMain && m_off == m_savedOff
					&& m_mainId == m_savedMainId && m_offId == m_savedOffId))
					return;
				auto bag = HWP::SaveData::Player(plr.m_record);
				bag.SetString("firearms.mag.main-id", m_mainId);
				bag.SetString("firearms.mag.off-id", m_offId);
				bag.SetInt("firearms.mag.main", m_main);
				bag.SetInt("firearms.mag.off", m_off);
				bag.SetInt("firearms.mag.total", m_main + m_off);
				m_savedMain = m_main;
				m_savedOff = m_off;
				m_savedMainId = m_mainId;
				m_savedOffId = m_offId;
			}

			// An external partial change has no firing hand (debug setup, a new weapon
			// set, spawn restoration). Apportion only that change; natural shots retain
			// their exact hand. At a full shared refill both magazines are full.
			void SetTotal(int total)
			{
				int maximum = m_mainMax + m_offMax;
				total = min(maximum, max(0, total));
				m_main = min(m_mainMax, max(0, m_main));
				m_off = min(m_offMax, max(0, m_off));
				int current = m_main + m_off;
				if (total == current)
					return;
				if (total == maximum)
				{
					m_main = m_mainMax;
					m_off = m_offMax;
				}
				else if (total > current)
				{
					int extra = total - current;
					int freeMain = m_mainMax - m_main;
					int free = maximum - current;
					int addMain = min(freeMain, int(extra * float(freeMain) / max(1, free) + 0.5f));
					m_main += addMain;
					m_off += extra - addMain;
				}
				else
				{
					m_main = int(total * float(m_main) / max(1, current) + 0.5f);
					m_off = total - m_main;
				}
			}

			void Sync(PlayerBase@ plr)
			{
				auto def = ActorBuffStackDef::Get(CLIP);
				if (plr is null || plr.m_record is null || def is null)
					return;
				int raw = max(0, plr.GetStacks(def));
				int maximum = max(0, ClipMax(plr, def));
				string mainId = MagazineItemId(plr.m_record, false);
				string offId = MagazineItemId(plr.m_record, true);
				int baseMain = BaseMagazine(mainId), baseOff = BaseMagazine(offId);
				int baseTotal = baseMain + baseOff;
				int mainMax = baseTotal <= 0 ? 0 : int(maximum * float(baseMain) / baseTotal + 0.5f);
				int offMax = baseTotal <= 0 ? 0 : maximum - mainMax;
				bool changed = !m_initialized || mainId != m_mainId || offId != m_offId;
				m_mainMax = mainMax;
				m_offMax = offMax;
				if (changed)
				{
					m_mainId = mainId;
					m_offId = offId;
					bool first = !m_initialized;
					m_main = m_off = 0;
					m_pending = 0;
					m_observed = raw;
					m_restorePending = false;
					m_initialized = true;
					@m_actor = plr;
					if (!first || !RestoreStored(plr, raw))
						SetTotal(raw);
					Persist(plr);
					return;
				}
				if (m_actor !is plr)
				{
					// UpdateFill restores the shared clip after the new actor's markers
					// arrive. Keep a known unequal split while that actor still has0.
					@m_actor = plr;
					m_pending = 0;
					m_observed = raw;
					m_restorePending = raw == 0 && m_main + m_off > 0;
					if (!m_restorePending)
						SetTotal(raw);
					Persist(plr);
					return;
				}
				if (m_restorePending)
				{
					if (raw > 0)
					{
						m_restorePending = false;
						m_observed = raw;
						SetTotal(raw);
						Persist(plr);
					}
					return;
				}
				int delta = raw - m_observed;
				if (delta < 0)
				{
					// Shot actions precede AddStacks(clip,-N). Match that native
					// debit against shots already counted; never subtract it twice.
					int matched = min(m_pending, -delta);
					m_pending -= matched;
					m_observed = raw;
				}
				else if (delta > 0)
				{
					m_pending = 0;
					m_observed = raw;
				}
				SetTotal(max(0, raw - m_pending));
				Persist(plr);
			}

			void Shot(PlayerBase@ plr, bool off)
			{
				Sync(plr);
				if (m_restorePending)
					return;
				// Native mixed pairs may borrow the last shared round after one gun
				// empties. Preserve that firing behavior and debit its remaining donor.
				if ((off && m_off > 0) || (!off && m_main <= 0))
				{
					if (m_off > 0) m_off--;
				}
				else if (m_main > 0)
					m_main--;
				m_pending++;
				Persist(plr);
			}

			int Rounds(PlayerBase@ plr, bool off)
			{
				Sync(plr);
				if (m_restorePending)
					return 0;
				return off ? m_off : m_main;
			}
		}

		array<MagazineState@> g_magazines;
		MagazineState@ MagazineFor(PlayerBase@ plr)
		{
			if (plr is null || plr.m_record is null)
				return null;
			for (uint i = 0; i < g_magazines.length(); i++)
			{
				if (g_magazines[i].m_id == plr.m_record.id && g_magazines[i].m_uniqueKey == plr.m_record.uniqueKey)
					return g_magazines[i];
			}
			auto state = MagazineState(plr.m_record);
			g_magazines.insertLast(state);
			return state;
		}

		void MagazineShot(Actor@ actor, bool off)
		{
			auto plr = cast<PlayerBase>(actor);
			if (plr is null || !IsFirearms(plr.m_record))
				return;
			auto state = MagazineFor(plr);
			if (state !is null)
				state.Shot(plr, off);
		}

		int MagazineRounds(PlayerBase@ plr, bool off)
		{
			auto state = MagazineFor(plr);
			return state is null ? 0 : state.Rounds(plr, off);
		}

		void UpdateMagazine()
		{
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			if (plr is null || !IsFirearms(plr.m_record))
				return;
			auto state = MagazineFor(plr);
			if (state !is null)
				state.Sync(plr);
		}

		// 0 for non-cartridge skills: spells, rifle gadgets and another weapon
		// retain their shared-clip bonus. Handgun rounds use their own gun skill.
		uint MagazineHandSkill(PlayerBase@ plr, bool off)
		{
			string id = MagazineItemId(plr.m_record, off);
			if (id.findFirst("hwp_glock_") == 0)
				return HashString(off ? "hwp_attack_glock_off" : "hwp_attack_glock");
			if (id.findFirst("hwp_hcannon_") == 0)
				return HashString(off ? "hwp_attack_hcannon_off" : "hwp_attack_hcannon");
			return 0;
		}
	}
}

namespace Modifiers
{
	class HWPFirearmsMagazineCrit : CritDamage
	{
		HWPFirearmsMagazineCrit(UnitPtr unit, SValue& params) { super(unit, params); }

		void Modify(PlayerRecord@ rec, PlayerStats@ stats, float intensity) override
		{
			auto plr = cast<PlayerBase>(rec.actor);
			int main = HWP::Firearms::BaseMagazine(HWP::Firearms::MagazineItemId(rec, false));
			int off = HWP::Firearms::BaseMagazine(HWP::Firearms::MagazineItemId(rec, true));
			float mainRounds = main > 0 ? HWP::Firearms::MagazineRounds(plr, false) : intensity;
			float offRounds = off > 0 ? HWP::Firearms::MagazineRounds(plr, true) : intensity;
			stats.SpellCritDamage += lerp(m_spellCritDmg, intensity);
			if (m_role != Role::OffHand)
				stats.MainHand.CritDamage += lerp(m_attackCritDmg, mainRounds);
			if (m_role != Role::MainHand)
				stats.OffHand.CritDamage += lerp(m_attackCritDmg, offRounds);
		}
	}
}

// Native DamageActor selects crit stats by DamageInfo.Weapon's skill type. A
// paired/mixed action can fire the other gun, so its round must identify that gun.
// Turret/other IOwnedUnit rounds keep their existing summon damage path unchanged.
class HWPFirearmsGunDamage : PlayerDamage
{
	HWPFirearmsGunDamage(UnitPtr unit, SValue& params) { super(unit, params); }

	void FillDamage(Actor@ owner, IDamageTaker@ target, DamageInfo@ di, float intensity) override
	{
		PlayerDamage::FillDamage(owner, target, di, intensity);
		auto plr = cast<PlayerBase>(owner);
		if (plr is null || HWP::Firearms::FindSkill(plr, HashString("hwp_fs_steady")) is null)
			return;
		uint skill = HWP::Firearms::MagazineHandSkill(plr, !m_primary);
		if (skill != 0 && HWP::Firearms::FindSkill(plr, skill) !is null)
			di.Weapon = skill;
	}
}
