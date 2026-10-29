// Pets keep out of puzzle rooms and trap rooms. A Watcher per pet, a few
// times a second, looks for room units around the owner and around the pet:
//   - while the owner is in a room, the pet walks back out along the owner's
//     own path to the last spot of it that was clear of rooms, and idles there
//     (no pickups, no following, no skills); it rejoins when the owner leaves;
//   - while the owner is outside but the pet is in a room (it wandered in, or
//     the floor started there), the pet walks out the same way and waits
//     there until the owner moves on, so it does not wander straight back in,
//     or until the room is gone (its traps or buttons destroyed);
//   - a pet going back to its owner after either wait may cross a room on the
//     way, for up to REJOIN_MS or until it reaches them: an owner who crossed a
//     trap room is followed through it (20261028-132436: the pet walked in after
//     them, turned back out, waited, and so on, 237 px behind after 10 s).
// The way out is the owner's trail (positions recorded every CHECK_MS): the
// trail point nearest the pet, then along the trail, older or newer, to the
// nearest point that was clear. Those are places the owner walked, so the pet
// never cuts through a wall to reach them.
//
// The Pets package's pet classes (mods/pets PetClasses.as) own their Watcher
// (they are Owned) and skip their own Update while it parks them; the same
// parking serves the candle's Secret Sense there: the pet sets m_hold and
// m_holdPos (HWP::Pets::SkillRunner.UpdateSecrets) and the pet hovers there.
// Every other pet (vanilla, without the Pets package) is driven by
// PetRooms.as, which holds its own Update off while it is parked.
//
// Room units are fetched by position (FetchAllUnits: buttons have no collision,
// so QueryCircle never returns them) and recognised by producer path:
//   - puzzle: doodads/buttons/* (magic / number / lever buttons, also in HWP's
//     Constellation) and anything with "puzzle" in the path (prefabs/puzzles/*,
//     puzzle_brazier, puzzle_chance, doodads/hwp/puzzle_constellation_dot);
//     one is enough;
//   - trap: anything under a traps/ folder (doodads/traps/* floor spikes and
//     pressure plates, shooters, sawblades, haunted statues, tripwires, mines;
//     the campaign's doodads/hwp/traps/*), but not traps/projectiles/ (the
//     arrows and fireballs they shoot); TRAP_COUNT spots of them, units within
//     TRAP_SPOT px of each other being one spot (a campaign glyph is two units,
//     the glyph and its _explode), so the campaign's glyphs and spike patches
//     in hallways do not make the hallway a room (20261028-123720: one glyph
//     129 px from the floor start parked the pet there, skills and all).
namespace HWP
{
	namespace PetWait
	{
		const int CHECK_MS = 400;
		const int TRAP_COUNT = 3;
		const float TRAP_SPOT = 12.0f;
		const uint TRAIL_MAX = 64;       // owner positions kept: the way back out
		const float TRAIL_STEP = 16.0f;  // px the owner moves before the next one
		const float TRAIL_JUMP = 320.0f; // a bigger move is a teleport: the trail starts over
		const float MOVE_ON = 96.0f;     // px the owner moves before a pet that left a room rejoins
		const int REJOIN_MS = 5000;      // a rejoining pet may cross a room this long...
		const float REJOIN_NEAR = 48.0f; // ...or until it is this near its owner

		bool g_enabled = true;
		int g_radius = 120;
		bool g_debug = false; // petwait.debug (not on the settings page): each change logged

		void RefreshSettings()
		{
			g_enabled = HWP::Settings::GetBool("petwait.enabled", true);
			g_radius = HWP::Settings::GetInt("petwait.radius", 120);
			g_debug = HWP::Settings::GetBool("petwait.debug", false);
		}

		string At(vec2 v) { return "(" + int(v.x) + ", " + int(v.y) + ")"; }

		string ProducerPath(UnitPtr unit)
		{
			if (!unit.IsValid())
				return "";
			auto prod = unit.GetUnitProducer();
			if (prod is null)
				return "";
			return prod.GetResourceName();
		}

		bool IsPuzzlePath(const string &in path)
		{
			return path.findFirst("doodads/buttons/") == 0 || path.findFirst("puzzle") >= 0;
		}

		bool IsTrapPath(const string &in path)
		{
			return path.findFirst("traps/") >= 0 && path.findFirst("traps/projectiles/") < 0;
		}

		// a pet class that runs its own Watcher (the Pets package's); PetRooms.as drives the rest
		interface Owned
		{
		}

		bool IsPuzzleUnit(UnitPtr unit)
		{
			return IsPuzzlePath(ProducerPath(unit));
		}

		// In a puzzle or trap room: a puzzle unit, or TRAP_COUNT trap spots, within the radius.
		// The fetch is coarse (it returns units well past the radius), so the distance is
		// checked here; without it the pet kept waiting 220 px from a puzzle, skills and all.
		bool InRoom(vec2 pos)
		{
			auto results = g_scene.FetchAllUnits(~0, pos, g_radius);
			float maxSq = float(g_radius) * float(g_radius);
			array<vec2> traps;
			for (uint i = 0; i < results.length(); i++)
			{
				UnitPtr unit = results[i];
				if (!unit.IsValid() || unit.IsDestroyed())
					continue;
				if (distsq(pos, xy(unit.GetPosition())) > maxSq)
					continue;
				string path = ProducerPath(unit);
				if (IsPuzzlePath(path))
					return true;
				if (!IsTrapPath(path))
					continue;
				vec2 at = xy(unit.GetPosition());
				bool known = false;
				for (uint j = 0; j < traps.length() && !known; j++)
					known = dist(traps[j], at) < TRAP_SPOT;
				if (known)
					continue;
				traps.insertLast(at);
				if (int(traps.length()) >= TRAP_COUNT)
					return true;
			}
			return false;
		}

		// Back to following after a wait or a hover: straight to the owner. The parking spot is
		// on the owner's path, often a corner of it against a wall, where a walking pet's own
		// pathfind can fail; an Idle pet then never moves (Idle has no straight-line fallback
		// and picks a new idle target on every failed search) until the owner is past the
		// 350 px leash (20261018-144852: still 200 px off 9 s after the owner left).
		// MovingToPlayer walks straight while no path is in and, if the search fails, puts the
		// pet by the owner, as the base does past the leash.
		void Rejoin(MiniPet@ pet, vec2 ownerPos)
		{
			pet.ClearTarget();
			pet.m_targetingDelay = 0;
			if (pet.IsHusk())
				return;
			pet.SetTarget(ownerPos, PetState::MovingToPlayer);
			pet.m_targetingDelay = 1500;
			auto walking = cast<MiniPetWalking>(pet);
			if (walking !is null)
				walking.m_pathTimeout = 1500;
		}

		class Watcher
		{
			int m_timer;
			bool m_waiting;  // the owner is in a room: the pet waits outside
			bool m_leaving;  // the pet was in a room: it walks out and waits for the owner to move on
			bool m_flying;
			vec2 m_leftAt;   // where the owner stood when the pet left a room
			vec2 m_roomAt;   // where the pet stood in it
			int m_rejoin;    // ms left of a rejoin that may cross rooms
			array<vec2> m_trail;
			array<bool> m_trailClear;
			array<vec2> m_route; // the way to the parking spot; the last point is the spot
			float m_angle;
			bool m_hold;     // set by the pet each frame: park at m_holdPos (before rooms)
			bool m_wasHold;
			vec2 m_holdPos;

			void Record(vec2 ownerPos, bool clear)
			{
				uint n = m_trail.length();
				if (n > 0)
				{
					float d = dist(m_trail[n - 1], ownerPos);
					if (d > TRAIL_JUMP)
					{
						m_trail.resize(0);
						m_trailClear.resize(0);
					}
					else if (d < TRAIL_STEP)
					{
						m_trailClear[n - 1] = m_trailClear[n - 1] && clear;
						return;
					}
				}
				m_trail.insertLast(ownerPos);
				m_trailClear.insertLast(clear);
				if (m_trail.length() > TRAIL_MAX)
				{
					m_trail.removeAt(0);
					m_trailClear.removeAt(0);
				}
			}

			// A trail point that was clear and still is (a trap spawned since makes it a room).
			bool Clear(int i)
			{
				if (m_trailClear[i] && InRoom(m_trail[i]))
					m_trailClear[i] = false;
				return m_trailClear[i];
			}

			// The way out from the pet: to the trail point nearest it, then along the trail to the
			// nearest point that is clear (fewest steps, older or newer). Empty: no clear point.
			void Route(vec2 petPos)
			{
				m_route.resize(0);
				int n = int(m_trail.length());
				if (n == 0)
					return;
				int near = 0;
				for (int i = 1; i < n; i++)
					if (distsq(petPos, m_trail[i]) < distsq(petPos, m_trail[near]))
						near = i;
				int best = -1;
				for (int k = 0; k < n && best < 0; k++)
				{
					if (near - k >= 0 && Clear(near - k))
						best = near - k;
					else if (near + k < n && Clear(near + k))
						best = near + k;
				}
				if (best < 0)
					return;
				int step = best < near ? -1 : 1;
				for (int i = near; ; i += step)
				{
					m_route.insertLast(m_trail[i]);
					if (i == best)
						break;
				}
			}

			void Park(MiniPet@ pet, vec2 petPos)
			{
				Route(petPos);
				if (m_route.length() == 0)
					m_route.insertLast(petPos);
				pet.ClearTarget();
			}

			void Note(const string &in what, vec2 ownerPos, vec2 petPos)
			{
				if (!g_debug)
					return;
				string route = m_route.length() == 0 ? "-" : (m_route.length() + " to " + At(m_route[m_route.length() - 1]));
				HWP::Log("petrooms", what + ": owner " + At(ownerPos) + " pet " + At(petPos) + ", route " + route
					+ ", trail " + m_trail.length());
			}

			// true = the pet is parked this frame and the base Update must be skipped
			bool Update(int dt, MiniPet@ pet)
			{
				return Step(dt, pet, pet.m_owner);
			}

			bool Step(int dt, MiniPet@ pet, PlayerBase@ owner)
			{
				if (owner is null || !owner.m_unit.IsValid() || !pet.m_unit.IsValid())
					return false;

				vec2 ownerPos = xy(owner.m_unit.GetPosition());
				vec2 petPos = xy(pet.m_unit.GetPosition());
				m_rejoin = dist(ownerPos, petPos) <= REJOIN_NEAR ? 0 : m_rejoin - dt;
				m_timer -= dt;
				if (m_timer <= 0)
				{
					m_timer = CHECK_MS;
					bool on = g_enabled;
					bool ownerIn = on && InRoom(ownerPos);
					Record(ownerPos, !ownerIn);
					if (ownerIn)
					{
						if (!m_waiting && !m_leaving)
						{
							Park(pet, petPos);
							Note("owner in a room", ownerPos, petPos);
						}
						m_waiting = true;
						m_leaving = false;
					}
					else if (m_waiting)
					{
						m_waiting = false;
						m_rejoin = REJOIN_MS;
						Rejoin(pet, ownerPos);
						Note("owner out", ownerPos, petPos);
					}
					else if (m_leaving)
					{
						if (!on || dist(ownerPos, m_leftAt) >= MOVE_ON || !InRoom(m_roomAt))
						{
							m_leaving = false;
							m_rejoin = REJOIN_MS;
							Rejoin(pet, ownerPos);
							Note("left room, rejoining", ownerPos, petPos);
						}
					}
					else if (on && !m_hold && m_rejoin <= 0 && InRoom(petPos))
					{
						m_leaving = true;
						m_leftAt = ownerPos;
						m_roomAt = petPos;
						Park(pet, petPos);
						Note("pet in a room", ownerPos, petPos);
					}
				}

				if (m_wasHold && !m_hold)
					Rejoin(pet, ownerPos);
				else if (m_hold && !m_wasHold)
					pet.ClearTarget();
				m_wasHold = m_hold;
				if (!m_waiting && !m_leaving && !m_hold)
					return false;

				vec2 target;
				if (m_hold)
					target = m_holdPos;
				else
				{
					// past each waypoint to the next, the last one is the spot
					while (m_route.length() > 1 && dist(petPos, m_route[0]) <= 4.0f)
						m_route.removeAt(0);
					target = m_route.length() > 0 ? m_route[0] : petPos;
				}
				vec2 at = target;
				vec2 delta = target - petPos;
				float len = length(delta);
				float step = pet.m_speed * dt / 33.0f;
				if (len > step && len > 1.0f)
				{
					vec2 dir = delta / len;
					m_angle = atan(dir.y, dir.x);
					at = petPos + dir * step;
					pet.m_unit.SetPosition(at.x, at.y, 0, true);
					pet.m_unit.SetUnitScene(pet.m_animWalk.GetSceneName(m_angle), true);
				}
				else
				{
					pet.m_unit.SetPosition(target.x, target.y, 0, false);
					if (!m_hold && m_route.length() > 1)
						m_route.removeAt(0);
					if (m_flying)
						pet.m_unit.SetUnitScene(pet.m_animWalk.GetSceneName(m_angle), false);
					else
						pet.m_unit.SetUnitScene(pet.m_animIdle.GetSceneName(m_angle), false);
				}
				pet.m_stayPos = at; // where a vanilla pet's own Update keeps it while it has no target
				return true;
			}
		}
	}
}
