// Way Gates: teleport gates across the town. One stands in the town square (by the
// fountain of town_square_4, where the laststats notice board is) and one in front of
// every building the town has built: the middle of the building's bottom edge (its
// variation's grid footprint on the plot, TownRecord::PlaceBuilding), moved
// to the nearest free spot. Using a gate opens the list of the others (WayGateShop.as);
// a pick moves the local player there.
//
// Every machine builds the same gate list from the synced town record (Build); only the
// host spawns the units (actors, netsynced). A building upgrade reloads the town without
// a new Start and takes the units with it: once a second the host checks they are still
// there and spawns the whole set again when one is gone, as HWP::Town::Kept does. Every
// machine also rebuilds the list when a gate's menu opens, so a client's list follows the
// rebuilt town too.
// Settings: waygates.enabled (default on), waygates.square_x / square_y (the square's
// gate). `hwp waygates` lists the gates; `hwp waygates go <n>` takes the n-th (cheats).
namespace HWP
{
	namespace WayGates
	{
		const string GATE_UNIT = "doodads/hwp/hwp_waygate.unit";
		const string EFFECT = "effects/generic/other/spawn_smoke_puff.effect";
		const int SPAWN_DELAY_MS = 800;   // after the town's own units and core's placeables
		const int FREE_STEP = 8;          // the free-spot search: rings this far apart
		const int FREE_RINGS = 12;
		const float SAME_GATE = 40.0f;    // a gate within this of the user is "here"

		class Gate
		{
			string id;     // "square" or the building id
			string name;   // shown in the list
			vec2 pos;
			Gate(const string &in i, const string &in n, vec2 p) { id = i; name = n; pos = p; }
		}

		array<Gate@> g_gates;
		bool g_enabled = true;

		void RefreshSettings()
		{
			g_enabled = HWP::Settings::GetBool("waygates.enabled", true);
		}

		vec2 SquarePos()
		{
			return vec2(float(HWP::Settings::GetInt("waygates.square_x", -504)),
				float(HWP::Settings::GetInt("waygates.square_y", 196)));
		}

		// nothing solid in a 20x20 box at p (the probe's terrain test, wider for the pad).
		// Actors don't count: players, town folk and the gates themselves move or go, and
		// the spots must come out the same on every machine and every reload.
		bool Free(vec2 p)
		{
			auto hits = g_scene.QueryRect(p, 20, 20, ~0, RaycastType::Any);
			for (uint i = 0; i < hits.length(); i++)
			{
				if (cast<Actor>(hits[i].GetScriptBehavior()) is null)
					return false;
			}
			return true;
		}

		// the nearest free spot to want, in rings FREE_STEP apart; want itself when none
		vec2 NearestFree(vec2 want)
		{
			if (Free(want))
				return want;
			for (int r = 1; r <= FREE_RINGS; r++)
			{
				float d = float(r * FREE_STEP);
				// south first (the street in front of a building), then the sides, then north
				array<vec2> ring = { vec2(0, d), vec2(-d, d), vec2(d, d), vec2(-d, 0), vec2(d, 0),
					vec2(-d, -d), vec2(d, -d), vec2(0, -d) };
				for (uint i = 0; i < ring.length(); i++)
				{
					if (Free(want + ring[i]))
						return want + ring[i];
				}
			}
			return want;
		}

		// where SpawnTown put each plotless building (its placement cell): the same walk as
		// TownRecord.PlaceTownSegment / PlaceTownPlacedPrefab / PlaceBuilding, from the base
		// segment through every segment variation and building, without placing anything
		dictionary g_cells;

		void Walk(uint id, ivec2 at, int depth)
		{
			if (depth > 8)
				return;
			auto seg = MissionPrefabDef::Get(id);
			if (seg !is null)
			{
				if (seg.m_parent !is null)
					@seg = seg.m_parent;
				// a segment's children land at at + their pos, whichever variation is used
				array<MissionPrefabDef@> cand = { seg };
				for (uint i = 0; i < seg.m_variations.length(); i++)
					cand.insertLast(seg.m_variations[i]);
				for (uint c = 0; c < cand.length(); c++)
				{
					for (uint i = 0; i < cand[c].m_placedPrefabs.length(); i++)
						Walk(cand[c].m_placedPrefabs[i].m_id, at + cand[c].m_placedPrefabs[i].m_pos, depth + 1);
				}
			}
			auto def = g_currTownRecord.GetBuildingDef(id);
			if (def is null)
				return;
			if (!g_cells.exists(def.m_id))
				g_cells.set(def.m_id, at);
			auto placed = g_currTownRecord.GetPlacedBuildingWithoutPlot(def);
			if (placed !is null && def.m_variations.length() > 0)
			{
				auto v = def.m_variations[min(def.m_variations.length() - 1, placed.variation)];
				v.UnpackData();
				for (uint i = 0; i < v.m_placedPrefabs.length(); i++)
					Walk(v.m_placedPrefabs[i].m_id, at + v.m_placedPrefabs[i].m_pos + v.m_gridOffset, depth + 1);
			}
			else
			{
				for (uint i = 0; i < def.m_unbuiltPlacedPrefabs.length(); i++)
					Walk(def.m_unbuiltPlacedPrefabs[i].m_id, at + def.m_unbuiltPlacedPrefabs[i].m_pos, depth + 1);
			}
		}

		void FindCells()
		{
			g_cells.deleteAll();
			auto bases = MissionPrefabDef::GetPossiblePrefabs(HashString("town_segment_base"));
			for (uint b = 0; b < bases.length(); b++)
			{
				// PlaceTownSegment(grid, base, ivec2()): children at their pos + the base's offset
				for (uint i = 0; i < bases[b].m_placedPrefabs.length(); i++)
					Walk(bases[b].m_placedPrefabs[i].m_id, bases[b].m_placedPrefabs[i].m_pos + bases[b].m_gridOffset, 0);
			}
		}

		// in front of a placed building: the middle of its footprint's bottom edge, a
		// cell further south, at the nearest free spot
		bool FrontOf(BuildingManagement::PlacedBuilding@ b, vec2 &out pos)
		{
			if (b.buildingDef.m_variations.length() == 0)
				return false;
			// the cell PlaceBuilding gets: the plot's, or where a segment placed the building.
			// Vanilla buildings are all plotless and their variations carry no grid size, so
			// they take the fallback below: three cells south of that cell (near the vendor in
			// the walk-in buildings, measured at every building's last tier)
			ivec2 at;
			auto plot = g_currTownRecord.GetPlot(b.plotHash);
			if (plot !is null)
				at = ivec2(int(plot.Position.x / 16), int(plot.Position.y / 16));
			else if (b.plotHash != 0 || !g_cells.get(b.buildingDef.m_id, at))
				return false;
			auto v = b.buildingDef.m_variations[min(b.buildingDef.m_variations.length() - 1, b.variation)];
			v.UnpackData();
			// the footprint's top-left cell: PlaceBuilding copies the pattern to pos - m_gridOffset
			// (m_gridOffset is the sval's grid-pos negated, BuildingDef.as UnpackData)
			ivec2 cell = at - v.m_gridOffset;
			vec2 want = v.m_gridSz.y > 0
				? vec2(float(cell.x * 16) + float(v.m_gridSz.x * 16) / 2.0f, float((cell.y + v.m_gridSz.y) * 16) + 16.0f)
				: vec2(float(at.x * 16), float(at.y * 16) + 48.0f);
			pos = NearestFree(want);
			return true;
		}

		string BuildingName(BuildingManagement::BuildingDef@ def)
		{
			string name = def.m_variations.length() > 0 ? Resources::GetString(def.m_variations[0].m_name) : "";
			return name.isEmpty() ? def.m_id : name;
		}

		// the town's gates: the square first, then the built buildings by name
		void Build()
		{
			g_gates.removeRange(0, g_gates.length());
			if (g_currTownRecord is null)
				return;
			FindCells();
			g_gates.insertLast(Gate("square", Resources::GetString(".hwp.waygates.square"), NearestFree(SquarePos())));
			array<Gate@> built;
			for (uint i = 0; i < g_currTownRecord.m_buildings.length(); i++)
			{
				auto b = g_currTownRecord.m_buildings[i];
				if (b is null || b.buildingDef is null)
					continue;
				vec2 p;
				if (FrontOf(b, p))
					built.insertLast(Gate(b.buildingDef.m_id, BuildingName(b.buildingDef), p));
				else
					HWP::Log("waygates", "no gate for " + b.buildingDef.m_id + ": not on a plot or a town segment");
			}
			// by name (an insertion sort: array.sort throws on an empty array)
			for (uint i = 0; i < built.length(); i++)
			{
				uint at = 1;
				while (at < g_gates.length() && g_gates[at].name < built[i].name)
					at++;
				g_gates.insertAt(at, built[i]);
			}
		}

		string List()
		{
			string s;
			for (uint i = 0; i < g_gates.length(); i++)
				s += (i > 0 ? "; " : "") + i + " " + g_gates[i].id + " at " + int(g_gates[i].pos.x) + "," + int(g_gates[i].pos.y);
			return s;
		}

		// the gate at this spot (-1: none)
		int Here(vec2 at)
		{
			for (uint i = 0; i < g_gates.length(); i++)
			{
				if (distsq(g_gates[i].pos, at) <= SAME_GATE * SAME_GATE)
					return int(i);
			}
			return -1;
		}

		// the local player to gate n: a puff where they stood and where they land,
		// UnitTeleported so the other machines snap the unit instead of walking it
		bool Go(int n)
		{
			if (n < 0 || n >= int(g_gates.length()))
				return false;
			auto plr = GetLocalPlayer();
			if (plr is null)
				return false;
			vec3 from = plr.m_unit.GetPosition();
			vec2 to = g_gates[n].pos + vec2(0, 4);
			PlayEffect(EFFECT, from);
			(Network::Message("UnitTeleported") << plr.m_unit << to).SendToAll();
			plr.m_unit.SetPosition(xyz(to));
			PlayEffect(EFFECT, xyz(to));
			HWP::Log("waygates", "to " + g_gates[n].id + ": " + int(from.x) + "," + int(from.y) + " -> " + int(to.x) + "," + int(to.y));
			return true;
		}

		// hwp waygates [go <n>]
		void Cmd(array<string>@ args)
		{
			if (args.length() >= 2 && args[0] == "go")
			{
				if (!HWP::Cheats::On())
					return;
				HWP::Commands::Reply(Go(parseInt(args[1])) ? "way gate " + args[1] : "no way gate " + args[1]);
				return;
			}
			HWP::Commands::Reply("way gates (" + (g_enabled ? "on" : "off") + "): " + g_gates.length() + ": " + List());
		}
	}
}

namespace Modules
{
	class HWPWayGatesModule : Module, HWP::ModuleStart
	{
		bool m_placed = true;
		int m_delay = 0;
		int m_watch = 0;
		HWP::Town::Units m_units;
		bool m_broken = false;

		HWPWayGatesModule()
		{
			super("hwp-waygates");
			HWP::Commands::Register("waygates", " the town's way gates; cheats: 'go <n>' takes the n-th", HWP::Commands::Handler(HWP::WayGates::Cmd));
		}

		void Start(StartMode sMode)
		{
			HWP::WayGates::RefreshSettings();
			m_placed = false;
			m_delay = 0;
			m_watch = 0;
			m_units.removeRange(0, m_units.length());
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("waygates", "HWPWayGatesModule.UpdateFrame"))
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
			if (paused || !g_inTown)
				return;
			if (!m_placed)
			{
				m_delay += ms;
				if (m_delay < HWP::WayGates::SPAWN_DELAY_MS)
					return;
				m_placed = true;
				Place();
				return;
			}
			m_watch += ms;
			if (m_watch < HWP::Town::WATCH_MS)
				return;
			m_watch = 0;
			HWP::WayGates::RefreshSettings();
			if (!Network::IsServer() || m_broken || !HWP::WayGates::g_enabled)
				return;
			bool gone = m_units.length() == 0;
			for (uint i = 0; i < m_units.length() && !gone; i++)
				gone = !m_units.Live(i);
			if (gone)
			{
				HWP::Log("waygates", "the town was rebuilt, placing the gates again");
				Place();
			}
		}

		// every machine: the list; the host: the units
		void Place()
		{
			HWP::WayGates::Build();
			if (!HWP::WayGates::g_enabled)
				return;
			HWP::Log("waygates", HWP::WayGates::g_gates.length() + " gate(s): " + HWP::WayGates::List());
			if (!Network::IsServer())
				return;
			for (uint i = 0; i < m_units.length(); i++)
			{
				if (m_units.Live(i))
					m_units[i].Destroy();
			}
			m_units.removeRange(0, m_units.length());
			auto prod = Resources::GetUnitProducer(HWP::WayGates::GATE_UNIT);
			if (prod is null)
			{
				HWP::LogError("waygates", "missing " + HWP::WayGates::GATE_UNIT);
				m_broken = true;
				return;
			}
			for (uint i = 0; i < HWP::WayGates::g_gates.length(); i++)
				m_units.insertLast(prod.Produce(g_scene, xyz(HWP::WayGates::g_gates[i].pos)));
		}
	}
}
