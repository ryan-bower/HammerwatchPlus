// HoH1 teleporters in generated floors. A pad (doodads/hwp/teleport_pad.unit, set
// hwp_teleporters, placed by Traps.as at generation) takes whoever uses it to one fixed
// spot elsewhere on the floor, the same spot every use, unknown until stepped through:
// chosen at generation from the floor's other prefabs (a trap, a puzzle or a treasure
// room when the floor has one, else the farthest floor cell). The host owns the
// destination table (HWP::Campaign::Teleporters::g_links, pad position -> destination)
// and moves the unit with the vanilla UnitTeleported message, as WorldScript::Teleport
// does; a client's use reaches the host through the engine's UseUnitSecure path
// (netsync="position" on the unit), which calls NetUse(husk) on the host.
// The HoH1 teleport effect (hoh1/effects/animations/player_teleport_mt.effect) plays
// when the import is packed, the vanilla spawn puff otherwise. Setting
// campaign.teleporters (default on). `hwp campaign teleporter [dx dy]` spawns a pad at
// the player with its destination dx,dy away (cheats on).
namespace HWP
{
	namespace Campaign
	{
		namespace Teleporters
		{
			const string PAD_UNIT = "doodads/hwp/teleport_pad.unit";
			const string SET = "hwp_teleporters";
			const string HOH1_EFFECT = "hoh1/effects/animations/player_teleport_mt.effect";
			const string FALLBACK_EFFECT = "effects/generic/other/spawn_smoke_puff.effect";
			const float MATCH = 24.0f;    // a pad within this of a table entry owns it

			class Link
			{
				vec2 pad;
				vec2 dest;
				string why;
				Link(vec2 p, vec2 d, const string &in w) { pad = p; dest = d; why = w; }
			}

			array<Link@> g_links;      // this floor's generation result (host)
			bool g_enabled = true;

			void RefreshSettings()
			{
				// campaign.enabled off (the settings page's switch) turns them off with the rest
				g_enabled = HWP::Settings::GetBool("campaign.enabled", true) && HWP::Settings::GetBool("campaign.teleporters", true);
			}

			void Clear()
			{
				g_links.removeRange(0, g_links.length());
			}

			void Add(vec2 pad, vec2 dest, const string &in why)
			{
				g_links.insertLast(Link(pad, dest, why));
			}

			bool Lookup(vec2 pad, vec2 &out dest, string &out why)
			{
				for (uint i = 0; i < g_links.length(); i++)
				{
					if (distsq(g_links[i].pad, pad) <= MATCH * MATCH)
					{
						dest = g_links[i].dest;
						why = g_links[i].why;
						return true;
					}
				}
				return false;
			}

			string Effect()
			{
				return Resources::GetEffect(HOH1_EFFECT) !is null ? HOH1_EFFECT : FALLBACK_EFFECT;
			}

			// hwp campaign teleporter [dx dy]: a pad under the player, destination dx,dy away
			void Cheat(array<string>@ args)
			{
				if (!HWP::Cheats::On())
					return;
				if (!Network::IsServer())
				{
					HWP::Commands::Reply("host only");
					return;
				}
				auto plr = GetLocalPlayer();
				if (plr is null)
				{
					HWP::Commands::Reply("no player in the world");
					return;
				}
				int dx = HWP::Cheats::IntArg(args, 1, 200);
				int dy = HWP::Cheats::IntArg(args, 2, 0);
				auto prod = Resources::GetUnitProducer(PAD_UNIT);
				if (prod is null)
				{
					HWP::Commands::Reply("unit " + PAD_UNIT + " missing");
					return;
				}
				vec3 at = plr.m_unit.GetPosition();
				vec2 dest = xy(at) + vec2(dx, dy);
				Add(xy(at), dest, "cheat");
				UnitPtr pad = prod.Produce(g_scene, at);
				HWPTeleportPad@ beh = null;
				if (pad.IsValid())
					@beh = cast<HWPTeleportPad>(pad.GetScriptBehavior());
				if (beh !is null)
					beh.Resolve();
				HWP::Commands::Reply("teleport pad " + (pad.IsValid() ? int(pad.GetId()) : 0) + " at " + int(at.x) + "," + int(at.y) + " -> " + int(dest.x) + "," + int(dest.y) + "; step on it and press use (gl use teleport_pad)");
			}
		}
	}
}

class HWPTeleportPad : IUsable
{
	UnitPtr m_unit;
	vec2 m_dest;
	bool m_resolved = false;
	string m_why;
	int m_uses = 0;

	// Only the generation table is read here: the unit is being fabricated, so the
	// scene fallback (other units' positions) waits for the first use.
	HWPTeleportPad(UnitPtr unit, SValue& params)
	{
		m_unit = unit;
		if (Network::IsServer() && HWP::Campaign::Teleporters::Lookup(xy(unit.GetPosition()), m_dest, m_why))
		{
			m_resolved = true;
			HWP::Log("campaign", "teleporter at " + int(unit.GetPosition().x) + "," + int(unit.GetPosition().y) + " -> " + int(m_dest.x) + "," + int(m_dest.y) + " (" + m_why + ")");
		}
	}

	// the generation table first; a pad without an entry (a save reload, the cheat's
	// pad after a restart) picks the farthest trap on the floor, else the farthest enemy
	void Resolve()
	{
		if (m_resolved)
			return;
		vec2 here = xy(m_unit.GetPosition());
		if (HWP::Campaign::Teleporters::Lookup(here, m_dest, m_why))
		{
			m_resolved = true;
			HWP::Log("campaign", "teleporter at " + int(here.x) + "," + int(here.y) + " -> " + int(m_dest.x) + "," + int(m_dest.y) + " (" + m_why + ")");
			return;
		}
		array<string> kinds = { "DangerAreaBehavior", "ProximityTrap", "TripMine", "Chest" };
		float best = 0;
		for (uint k = 0; k < kinds.length(); k++)
		{
			auto units = g_scene.FetchAllUnitsWithBehavior(kinds[k]);
			for (uint i = 0; i < units.length(); i++)
			{
				float d = distsq(xy(units[i].GetPosition()), here);
				if (d > best && d > 160 * 160)
				{
					best = d;
					m_dest = xy(units[i].GetPosition()) + vec2(0, 24);
					m_why = "near " + units[i].GetDebugName();
					m_resolved = true;
				}
			}
		}
		if (!m_resolved)
		{
			auto enemies = g_scene.FetchAllActorsWithOtherTeam(g_team_player);
			for (uint i = 0; i < enemies.length(); i++)
			{
				float d = distsq(xy(enemies[i].GetPosition()), here);
				if (d > best && d > 160 * 160)
				{
					best = d;
					m_dest = xy(enemies[i].GetPosition());
					m_why = "an enemy pack";
					m_resolved = true;
				}
			}
		}
		if (m_resolved)
			HWP::Log("campaign", "teleporter at " + int(here.x) + "," + int(here.y) + " -> " + int(m_dest.x) + "," + int(m_dest.y) + " (" + m_why + ", picked at use)");
	}

	SValue@ Save()
	{
		SValueBuilder sb;
		sb.PushDictionary();
		sb.PushBoolean("resolved", m_resolved);
		sb.PushVector2("dest", m_dest);
		sb.PushInteger("uses", m_uses);
		sb.PopDictionary();
		return sb.Build();
	}

	void Load(SValue@ data)
	{
		auto r = data.GetDictionaryEntry("resolved");
		auto d = data.GetDictionaryEntry("dest");
		auto u = data.GetDictionaryEntry("uses");
		if (r !is null && d !is null && r.GetBoolean())
		{
			m_resolved = true;
			m_dest = d.GetVector2();
			m_why = "saved";
		}
		if (u !is null)
			m_uses = u.GetInteger();
	}

	// host only: the unit (a Player or a PlayerHusk) goes to the fixed spot
	void Teleport(UnitPtr who)
	{
		if (!Network::IsServer() || !who.IsValid())
			return;
		Resolve();
		if (!m_resolved)
		{
			HWP::Log("campaign", "teleporter: no destination on this floor, nothing happens");
			return;
		}
		vec3 from = who.GetPosition();
		string fx = HWP::Campaign::Teleporters::Effect();
		PlayEffect(fx, from);
		(Network::Message("UnitTeleported") << who << m_dest).SendToAll();
		who.SetPosition(xyz(m_dest));
		PlayEffect(fx, xyz(m_dest));
		m_uses++;
		HWP::Log("campaign", "teleporter: " + who.GetDebugName() + " " + int(from.x) + "," + int(from.y) + " -> " + int(m_dest.x) + "," + int(m_dest.y) + " (use " + m_uses + ", " + m_why + ")");
	}

	// IUsable
	UnitPtr GetUseUnit() { return m_unit; }
	bool CanUse(PlayerBase@ player) { return HWP::Campaign::Teleporters::g_enabled; }
	UsableIcon GetIcon(Player@ player) { return UsableIcon::Generic; }
	ITooltip@ GetTooltip() { return null; }
	int UsePriority() { return -5; }
	bool IsInside(UnitPtr unit) { return m_unit.IsColliding(unit); }

	// the host's own player (and gl use on the host); on a client this runs after the
	// host already moved the player, and does nothing
	void Use(PlayerBase@ player)
	{
		if (player !is null)
			Teleport(player.m_unit);
	}

	// on the host for a client's use (PlayerHandler.UseUnitSecure); clients get it for
	// the host's use and ignore it
	void NetUse(PlayerHusk@ player)
	{
		if (player !is null)
			Teleport(player.m_unit);
	}

	void Collide(UnitPtr unit, vec2 pos, vec2 normal)
	{
		auto player = cast<Player>(unit.GetScriptBehavior());
		if (player !is null)
			player.AddUsable(this);
	}

	void EndCollision(UnitPtr unit)
	{
		auto player = cast<Player>(unit.GetScriptBehavior());
		if (player !is null)
			player.RemoveUsable(this);
	}
}
