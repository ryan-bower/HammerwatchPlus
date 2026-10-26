// HWP::CustomStat - a custom player stat's value (PlayerStats.m_customStats: Luck, the
// Firearms elemental chances, the keys and trinkets modules' stats), 0 when the player has
// none. Indexes the record's array in place, as PlayerBase does, instead of copying it.
namespace HWP
{
	float CustomStat(PlayerRecord@ rec, const string &in id)
	{
		if (rec is null)
			return 0;
		for (uint i = 0; i < rec.currStats.m_customStats.length(); i++)
		{
			auto stat = rec.currStats.m_customStats[i];
			if (stat !is null && stat.id == id && stat.svalue !is null)
				return stat.svalue.GetFloat();
		}
		return 0;
	}
}
