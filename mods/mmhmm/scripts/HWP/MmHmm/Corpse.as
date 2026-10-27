// Mm-hmm! on a revive: class swap PlayerCorpse -> HWPMmHmmCorpse (module.json; the one unit
// is players/player_corpse.unit). NetRevive runs on every peer with the reviver and the
// revived player (m_record) set; the base call destroys the corpse on the host, so both are
// read first. The machine of whichever of the two wears the hat says it; when both do, the
// host plays it once (the key names the revive). Not for a revive without a reviver
// (cht_revive passes the revived player as the reviver).
class HWPMmHmmCorpse : PlayerCorpse
{
	HWPMmHmmCorpse(UnitPtr unit, SValue& params)
	{
		super(unit, params);
		HWP::Log("mmhmm", "corpse: HWPMmHmmCorpse");
	}

	void NetRevive(PlayerRecord@ reviver, bool overridePosUsed = false, vec3 overridePos = vec3()) override
	{
		auto revived = m_record;
		if (reviver !is null && revived !is null && reviver !is revived)
		{
			bool mine = (reviver.local && HWP::MmHmm::Wearing(reviver)) || (revived.local && HWP::MmHmm::Wearing(revived));
			if (mine)
				HWP::MmHmm::Say("revive", "revive:" + revived.peer);
		}
		PlayerCorpse::NetRevive(reviver, overridePosUsed, overridePos);
	}
}
