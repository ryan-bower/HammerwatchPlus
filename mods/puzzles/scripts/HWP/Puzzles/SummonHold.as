// Summons wait outside puzzle rooms, the way pets do (pets: PetWait.as) and the
// way nothing of a player's follows them into a trap room's gauntlet. This is
// generic: every unit a player owns through PlayerRecord.summons (Crusaders,
// wolves, the Forgemaster's risen, anything RegisterSummon took) is held while
// its owner stands in a puzzle room, whatever class or module made it.
//
// The host runs it (summons are server actors; their positions sync). Every
// CHECK_MS it asks, per player, whether they are inside a puzzle room: inside a
// room this module placed (HWP::Puzzles::RoomAt, the recorded world rect) or
// within puzzles.summon_hold_radius px of a puzzle unit (buttons, levers,
// braziers, constellation dots: the rooms the vanilla matcher placed and the
// outdoor Constellation have no recorded walls). While inside, each live summon
// with a movement gets it disabled (ActorMovement.m_enabled, what every
// movement's Update checks first), its target cleared and its position pinned
// to the owner's last puzzle-free spot, spread in a small ring so they do not
// stack. The pin is re-applied every frame: PlayerOwnedActor's teleport leash
// (350 px) would otherwise pull them to the owner every half second once the
// owner is deep in the room. When the owner leaves, the movements are enabled
// again and the summons resume following. m_frozen is left alone: it is saved
// with the unit (mods/summons snapshots SaveUnit across floors).
//
// Settings (host, saved with the town): puzzles.summon_hold (default 1),
// puzzles.summon_hold_radius (default 120 px, the pets' petwait.radius).
namespace HWP
{
	namespace Puzzles
	{
		namespace SummonHold
		{
			const int CHECK_MS = 250;
			const float RING = 18.0f;  // px between held summons

			bool g_enabled = true;
			int g_radius = 120;

			void RefreshSettings()
			{
				g_enabled = HWP::Settings::GetBool("puzzles.summon_hold", true);
				g_radius = HWP::Settings::GetInt("puzzles.summon_hold_radius", 120);
			}

			void OnSettingChanged(const string &in key)
			{
				if (key.findFirst("puzzles.") == 0)
					RefreshSettings();
			}

			class Held
			{
				UnitPtr m_unit;
				array<ActorMovement@> m_disabled;
				vec2 m_pos;
			}

			class Owner
			{
				PlayerRecord@ m_rec;
				bool m_inside;
				bool m_hasFree;
				vec2 m_lastFree;
				int m_timer;
				array<Held@> m_held;
			}

			array<Owner@> g_owners;

			void Start()
			{
				ReleaseAll();
				g_owners.removeRange(0, g_owners.length());
				RefreshSettings();
			}

			// FetchAllUnits, not QueryCircle: the buttons have no collision shape (PetWait.as)
			bool NearPuzzleUnits(vec2 pos)
			{
				auto results = g_scene.FetchAllUnits(~0, pos, g_radius);
				float maxSq = float(g_radius) * float(g_radius);
				for (uint i = 0; i < results.length(); i++)
				{
					UnitPtr unit = results[i];
					if (!unit.IsValid() || unit.IsDestroyed())
						continue;
					if (distsq(pos, xy(unit.GetPosition())) > maxSq)
						continue;
					if (IsPuzzleUnit(unit))
						return true;
				}
				return false;
			}

			// where the owner is: "" outside, else the room's id or "puzzle units"
			string Inside(vec2 pos)
			{
				auto room = RoomAt(pos);
				if (room !is null)
					return room.m_id;
				if (NearPuzzleUnits(pos))
					return "puzzle units";
				return "";
			}

			bool IsLive(IOwnedUnit@ owned)
			{
				if (owned is null)
					return false;
				auto u = owned.GetUnit();
				if (!u.IsValid() || u.IsDestroyed())
					return false;
				auto actor = cast<Actor>(u.GetScriptBehavior());
				return actor is null || !actor.IsDead();
			}

			Owner@ OwnerOf(PlayerRecord@ rec)
			{
				for (uint i = 0; i < g_owners.length(); i++)
					if (g_owners[i].m_rec is rec)
						return g_owners[i];
				Owner o;
				@o.m_rec = rec;
				g_owners.insertLast(o);
				return o;
			}

			Held@ HeldOf(Owner@ owner, UnitPtr unit, vec2 base)
			{
				for (uint i = 0; i < owner.m_held.length(); i++)
					if (owner.m_held[i].m_unit == unit)
						return owner.m_held[i];
				Held h;
				h.m_unit = unit;
				// a ring around the spot: the k-th summon at angle k * 2.4 rad
				uint k = owner.m_held.length();
				float r = k == 0 ? 0.0f : RING * (1.0f + float(k - 1) / 6.0f);
				h.m_pos = base + vec2(cos(float(k) * 2.4f), sin(float(k) * 2.4f)) * r;
				owner.m_held.insertLast(h);
				return h;
			}

			void Hold(Owner@ owner, IOwnedUnit@ owned, vec2 base)
			{
				UnitPtr u = owned.GetUnit();
				ref@ b = u.GetScriptBehavior();
				ActorMovement@ mv = null;
				auto comp = cast<CompositeActorBehavior>(b);
				if (comp !is null)
					@mv = comp.m_movement;
				else
				{
					auto st = cast<StateActorBehavior>(b);
					if (st !is null)
						@mv = st.m_movement;
				}
				if (mv is null)
					return; // a stationary owned unit (a banner, a light): nothing to hold
				auto h = HeldOf(owner, u, base);
				if (mv.m_enabled)
				{
					mv.m_enabled = false;
					if (h.m_disabled.findByRef(mv) < 0)
						h.m_disabled.insertLast(mv);
				}
				auto actor = cast<Actor>(b);
				if (actor !is null)
					actor.SetTarget(null, -1);
				vec3 cur = u.GetPosition();
				if (distsq(xy(cur), h.m_pos) > 1.0f)
					u.SetPosition(h.m_pos.x, h.m_pos.y, cur.z, false);
			}

			void Release(Owner@ owner)
			{
				for (uint i = 0; i < owner.m_held.length(); i++)
				{
					auto h = owner.m_held[i];
					for (uint j = 0; j < h.m_disabled.length(); j++)
						h.m_disabled[j].m_enabled = true;
				}
				owner.m_held.removeRange(0, owner.m_held.length());
			}

			void ReleaseAll()
			{
				for (uint i = 0; i < g_owners.length(); i++)
				{
					Release(g_owners[i]);
					g_owners[i].m_inside = false;
				}
			}

			void Update(int ms)
			{
				if (!Network::IsServer() || !g_enabled)
				{
					if (g_owners.length() > 0)
						ReleaseAll();
					return;
				}
				for (uint p = 0; p < g_players.length(); p++)
				{
					auto rec = g_players[p];
					if (rec is null || rec.actor is null || !rec.actor.m_unit.IsValid())
						continue;
					vec2 ownerPos = xy(rec.actor.m_unit.GetPosition());
					auto owner = OwnerOf(rec);
					owner.m_timer -= ms;
					if (owner.m_timer <= 0)
					{
						owner.m_timer = CHECK_MS;
						string where = Inside(ownerPos);
						bool inside = !where.isEmpty();
						if (!inside)
						{
							owner.m_lastFree = ownerPos;
							owner.m_hasFree = true;
						}
						if (inside && !owner.m_inside)
						{
							int n = 0;
							for (uint i = 0; i < rec.summons.length(); i++)
								for (uint j = 0; j < rec.summons[i].m_units.length(); j++)
									if (IsLive(rec.summons[i].m_units[j]))
										n++;
							vec2 at = owner.m_hasFree ? owner.m_lastFree : ownerPos;
							HWP::Log("puzzles", "summons of " + rec.name + " held outside " + where + ": " + n + " unit(s) at " + int(at.x) + "," + int(at.y));
						}
						else if (!inside && owner.m_inside)
						{
							HWP::Log("puzzles", "summons of " + rec.name + " released: " + owner.m_held.length() + " unit(s)");
							Release(owner);
						}
						owner.m_inside = inside;
					}
					if (!owner.m_inside)
					{
						if (owner.m_held.length() > 0)
							Release(owner);
						continue;
					}
					vec2 base = owner.m_hasFree ? owner.m_lastFree : ownerPos;
					for (uint i = 0; i < rec.summons.length(); i++)
					{
						auto s = rec.summons[i];
						for (uint j = 0; j < s.m_units.length(); j++)
							if (IsLive(s.m_units[j]))
								Hold(owner, s.m_units[j], base);
					}
				}
			}
		}
	}
}
