// Dev Arena buff retune: patch a copy of the buff's sval and LoadParams it onto the def
// LoadActorBuff cached in g_actorBuffDefs (ActorBuff.as:301-324). Every ActorBuff built
// after that copies the new values (ActorBuff constructor reads def.m_duration etc.);
// buffs already running keep what they copied.
namespace HWP
{
namespace DevArena
{
	// the last sval each retuned buff was loaded from, so patches stack
	dictionary g_buffParams;   // path -> SValue@

	SValue@ BuffParams(const string &in path)
	{
		SValue@ sv;
		if (g_buffParams.get(path, @sv))
			return sv;
		return Resources::GetSValue(HashString(path));
	}

	ActorBuffDef@ RetuneBuff(const string &in path, const string &in param, const string &in value, string &out err)
	{
		auto def = LoadActorBuff(path);
		auto src = BuffParams(path);
		if (def is null || src is null)
		{
			err = "no buff '" + path + "'";
			return null;
		}
		auto copy = PatchCopy(src, param, value, err);
		if (copy is null)
			return null;
		def.LoadParams(copy);
		g_buffParams.set(path, @copy);
		HWP::Log("devarena", "buff " + path + " " + param + "=" + value);
		return def;
	}

	// the local player's running instance of def, or null
	ActorBuff@ PlayerBuff(ActorBuffDef@ def)
	{
		auto plr = LocalPlayer();
		if (plr is null || def is null)
			return null;
		for (uint i = 0; i < plr.m_buffs.m_buffs.length(); i++)
			if (plr.m_buffs.m_buffs[i].m_def is def)
				return plr.m_buffs.m_buffs[i];
		return null;
	}
}
}
