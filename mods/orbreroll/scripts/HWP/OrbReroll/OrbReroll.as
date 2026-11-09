// Orb rerolls per orb, not per run. Vanilla's orb picker (GiveSkillSphereMenu) lets a
// run reroll as often as the accomplishment rewards allow (m_rRerolls), counted in
// PlayerRecord.rerollsUsed, which the trinket picker shares. This module's override of the
// picker counts each orb's rerolls here instead, so every orb picked up gets the whole
// allowance, and the shadow curse cost (vanilla's 12 + 7 per reroll, scaled) starts over on
// each orb. The run's pool is left to the trinket picker.
//
// The count is keyed by the orb (its SkillSphere behaviour), which keeps its three picks
// while the picker is closed and opened again, so closing the picker never gives a reroll
// back. Script globals reset with the level, like the orb's picks (vanilla saves only
// whether the orb was used).
// Setting orbreroll.enabled (host): off gives vanilla's run-wide charges back.
namespace HWP
{
	namespace OrbReroll
	{
		array<SkillSphere@> g_orbs;
		array<int> g_used;

		bool Enabled()
		{
			return HWP::Settings::GetBool("orbreroll.enabled", true);
		}

		int Find(SkillSphere@ orb)
		{
			for (uint i = 0; i < g_orbs.length(); i++)
			{
				if (g_orbs[i] is orb)
					return int(i);
			}
			return -1;
		}

		// rerolls this orb has had
		int Used(SkillSphere@ orb)
		{
			if (orb is null)
				return 0;
			int i = Find(orb);
			return i < 0 ? 0 : g_used[i];
		}

		void Spend(SkillSphere@ orb)
		{
			if (orb is null)
				return;
			int i = Find(orb);
			if (i < 0)
			{
				g_orbs.insertLast(orb);
				g_used.insertLast(1);
			}
			else
				g_used[i]++;
		}
	}
}
