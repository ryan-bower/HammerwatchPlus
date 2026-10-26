// The Devil Forgemaster (Priest 4th spec, mods/specs): Necrotic Resurrection raises the intact
// bodies that Call of Heresy leaves, as summons made from the enemy's own unit.
// - HWPSpecsBody: an intact body (players/hwp/specs/forgemaster/bodies/<unit>, written by
//   tools/make_forgemaster_risen.py): the enemy's scenes, gray, on its side (a boss upright), no
//   collision, 60 s. The host rolls one on every enemy death while a Forgemaster is on the
//   floor (OnActorDestroyed). The glow effect is played on the Forgemaster's own screen only.
// - HWPSpecsRisen / HWPSpecsRisenState: the summon (.../risen/<unit>), a PlayerOwnedActor over
//   the enemy's params. After the vanilla Initialize it drops loot, experience and regen, swaps
//   every MeleeMovement for a follower movement (MeleeFollowerMovement, RangedFollowerMovement
//   for ranged kinds; passive, charge and worm movements stay: the leash teleports them along),
//   and strips the actions that drive a fight's script or spawn enemies (StripActions). Health
//   is the enemy's formula times nr-hp-pct, damage the enemy's times nr-dmg-base x nr-dmg-pct
//   x (1 + Heresy x coh-dmg), unhealable, decaying 1% every 3 s (a boss 9 s).
// - HWPSpecsResurrection: the skill. It needs a body within RAISE_RANGE and Heresy below 5;
//   its cast starts a channel on the caster's client (the raising buff: 3 s, elite 5 s, boss
//   10 s), and UpdateForgemaster finishes it: the skill's mana and cooldown are spent then (a
//   cancelled channel costs nothing) and the host raises the body (specs.raise request) and
//   answers specs.raised, which adds Heresy +1/+2/+3 on the caster's client; a body that was
//   gone when the host looked (another Forgemaster's raise, its time up) answers
//   specs.raise_denied: no Heresy, the cooldown given back. At max Divine Favor it is
//   Sacrificial Penance: 3 s, 50 mana, Heresy -(nr-penance + 1 elite + 2 boss), Divine Favor
//   spent, no cooldown.
// - The Heresy lunge: once per body, the first time the Forgemaster is within LUNGE_RANGE,
//   chance Heresy x coh-lunge: the priest dodges (its own Dash skill, so the dodge animation,
//   dust and sound) to EAT_BELOW px under the body, faces up and eats it (devouring buff 3 s:
//   rooted, rotation locked, a 1 px bob every EAT_BOB_MS, blood out of the body every
//   EAT_BLOOD_MS; the body goes when the eating ends), and Ravenous Lunge hits the enemies
//   around the body. A Penance channel dodges to the same spot, faces up and stands still while
//   a golden light pulses out of the body (penance_light.effect every PEN_LIGHT_MS), brighter
//   as the channel runs (the user, 2026-10-22).
// - A channel locks the priest onto its body (the user, 2026-10-25): the raising buff locks the
//   rotation, a raise faces the body at its start (SetAngle) and the Penance faces up after its
//   dodge; the Dash (ignore-blocking: silence never stops it) is pinned on cooldown for the
//   channel's remaining time (PinDash) so no lunge or dodge can start mid-channel. The channel's
//   effects: a necrotic beam from the priest to the body (necrotic_beam_1, green for a raise,
//   gold and straight up out of the body for a Penance) whose width grows with the progress
//   (EffectBehavior.SetParam each frame), a pulse on the body every CHANNEL_PULSE_MS scaled by
//   the progress (channel_pulse.effect / penance_light.effect), and a progress bar with a label
//   over the priest's head (RenderForgemaster, drawn by HWPSpecsModule.RenderFrame).
// - HWPSpecsRisenCap lifts the vanilla one-per-unit summon cap for risen producers; the owner's
//   client keeps the total at nr-count, the oldest going first (EnforceCap, as Player.as does).
// - HWPSpecsPyre (class swap of PyreUnitBehavior): Pyre Sacrifice lowers Heresy on use, and a
//   Forgemaster with Heresy can use a pyre with no curse (CanUse). The large pyre (a
//   WorldScript::Pyre, which no class swap reaches) is the module's override of
//   scripts/WorldScript/Pyre.as, with the same two rules (PyreHeresyAllows / PyreHeresyUsed).
// - PlayerInitialize hook: a Forgemaster gets Divine Favor level 1 for free, once per character.
namespace HWP
{
	namespace Specs
	{
		const uint NR = HashString("hwp_pri_necrotic_resurrection");
		const uint COH = HashString("hwp_pri_call_of_heresy");
		const uint DIVINE_FAVOR = HashString("divine_favor");
		const string HERESY = "heresy";
		const string RISEN_DIR = "players/hwp/specs/forgemaster/risen/";
		const string BODIES_DIR = "players/hwp/specs/forgemaster/bodies/";
		const int HERESY_BLOCK = 5;
		const int BODY_TTL = 60000;
		const int RAISE_RANGE = 150;
		const int LUNGE_RANGE = 40;
		const int LUNGE_HIT_RADIUS = 50;
		const int EAT_BELOW = 10;        // px under the body's origin the priest stands to eat or channel
		const int EAT_BOB_MS = 250;      // half period of the eating bob (1 px up, 1 px down)
		const int EAT_BLOOD_MS = 300;    // blood out of the body while eating
		const int PEN_LIGHT_MS = 150;    // the golden light's pulses during a Penance channel
		const int CHANNEL_PULSE_MS = 150; // a raise channel's pulses on the body
		const int DASH_PIN_MS = 50;      // the dash stays on cooldown this long past the channel's end
		const int BAR_W = 44;            // the channel bar over the priest's head
		const int BAR_H = 5;
		const int BAR_ABOVE = 34;        // px above the priest's origin
		const string BEAM = "effects/generic/raycast/necrotic_beam_1.effect";
		const int DODGE_MAX_MS = 600;    // a dodge to the body that takes longer is snapped there
		const uint DASH = HashString("dash_skill");
		const int BLOOM_RADIUS = 60;
		const int PENANCE_MANA = 50;
		const int CHANNEL_NORMAL = 3000;
		const int CHANNEL_ELITE = 5000;
		const int CHANNEL_BOSS = 10000;
		const int DECAY_NORMAL = 3000;
		const int DECAY_BOSS = 9000;
		// the least health a risen has (before the summon health stats): a yellow jacket's 60 died to
		// one bandit brute in two seconds (plan-forgemaster 20261022-085643), a body and Heresy for nothing
		const int RISEN_MIN_HP = 120;
		const float DECAY_STEP = 0.01f;

		class RaiseChannel
		{
			PlayerBase@ m_plr;
			UnitPtr m_body;
			bool m_penance;
			int m_left;
			int m_total;
			HWPSpecsResurrection@ m_skill;   // null for a channel the console forced
			PointCost@ m_cost;               // spent when the channel completes
			// a Penance: the dodge to under the body on the first frame, then the light
			bool m_dodge;
			bool m_dodging;
			int m_dodgeC;
			vec2 m_spot;
			int m_lightC;
			// the lock and the effects (the user, 2026-10-25)
			bool m_locked;      // facing set and the dash pinned (a Penance: after its dodge lands)
			float m_angle;      // the facing the channel holds, radians
			UnitPtr m_beam;     // the looping beam, its width grows with the progress
			int m_pulseC;
			int m_pulses;
			int m_dashRefused;  // dash presses seen while pinned
			int m_dashReal = -1;  // the dash's own cooldown when the pin first took over (-1: not pinned)
			int m_dashPinLeft;    // m_left at that moment, so UnpinDash knows how much of it ran out
			string m_label;     // the bar's text

			float Progress() { return m_total > 0 ? clamp(1.0f - float(m_left) / float(m_total), 0.0f, 1.0f) : 1.0f; }
		}
		// the last channel's measurements, kept after it ends for a slow reader (the test bot)
		int g_chanPulses, g_chanDashRefused, g_chanLockFacing = 999, g_chanBeamFrames;
		bool g_dashPinned = false;
		bool g_chanDrawn = false;

		// the priest eating a body after a lunge (the Forgemaster's own client)
		class Eating
		{
			PlayerBase@ m_plr;
			UnitPtr m_body;
			vec2 m_spot;
			bool m_dodging;
			int m_dodgeC;
			bool m_up;
			int m_bobC;
			int m_bloodC;
			int m_bobs;
			int m_bloods;
		}
		Eating@ g_eat;
		// the last eating's and Penance stance's measurements, kept after they end so a slow reader
		// (the test bot after a screenshot) still sees them: the facing in degrees (up is -90) and the
		// priest's offset from the body, recorded at each bob and each light pulse after the landing
		int g_eatBobs, g_eatBloods, g_eatFacing = 999;
		int g_penLights, g_penFacing = 999, g_penBeside = 999, g_penUnder = 999;

		array<HWPSpecsBody@> g_bodies;
		RaiseChannel@ g_channel;
		dictionary g_enemyUnits;
		dictionary g_risenRels;
		bool g_unitSetsBuilt = false;
		uint g_risenSeq = 0;
		int g_capC = 0;
		ScriptSprite@ g_hudHeresy;
		ScriptSprite@ g_hudHeresy5;
		bool g_hudHeresyHigh = false;
		// counters for `hwp specs` and the tests
		int g_bodiesSpawned = 0;
		int g_bodyRolls = 0;
		int g_raises = 0;
		int g_penances = 0;
		int g_lunges = 0;
		int g_blooms = 0;
		int g_capKills = 0;
		int g_decayDeaths = 0;
		int g_movesSwapped = 0;
		int g_actionsStripped = 0;
		string g_lastRaise = "";
		// `hwp forge trace`: every risen logs each skill it starts casting, and every 2 s which of
		// its skills are available (the tests' view of what a raised enemy does)
		bool g_trace = false;

		void ClearForgemaster()
		{
			g_bodies.removeRange(0, g_bodies.length());
			if (g_channel !is null)
				EndChannelFx(g_channel);
			@g_channel = null;
			g_dashPinned = false;
			g_chanDrawn = false;
			g_capC = 0;
		}

		void BuildUnitSets()
		{
			if (g_unitSetsBuilt)
				return;
			g_unitSetsBuilt = true;
			for (uint i = 0; i < ENEMY_UNITS.length(); i++)
				g_enemyUnits.set(ENEMY_UNITS[i], true);
			for (uint i = 0; i < RISEN_RELS.length(); i++)
				g_risenRels.set(RISEN_RELS[i], true);
		}

		bool IsEnemyUnit(const string &in path)
		{
			BuildUnitSets();
			return g_enemyUnits.exists(path);
		}

		// the "actors/..." path's part after actors/, when it is a raisable enemy; else ""
		string RisenRel(const string &in unitPath)
		{
			BuildUnitSets();
			if (unitPath.findFirst("actors/") != 0)
				return "";
			string rel = unitPath.substr(7);
			return g_risenRels.exists(rel) ? rel : "";
		}

		bool Alive(UnitPtr u) { return u.IsValid() && !u.IsDestroyed(); }

		bool HasActorTag(Actor@ a, const string &in tag)
		{
			return a !is null && (a.Tags & ApplyTag(0, g_actorTags.GetTag(tag))) != 0;
		}

		PlayerBase@ LocalForgemaster()
		{
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			if (plr is null || plr.m_record is null || !Learned(plr, COH))
				return null;
			return plr;
		}

		int Heresy(PlayerBase@ plr)
		{
			auto def = Stack(HERESY);
			return plr is null || def is null ? 0 : plr.GetStacks(def);
		}

		// on the player's own client (the buff list's authority for a player)
		void AddHeresy(PlayerBase@ plr, int n)
		{
			auto def = Stack(HERESY);
			if (plr is null || def is null || n == 0)
				return;
			plr.AddStacks(plr, def, n);
			Log("specs", "heresy " + (n > 0 ? "+" : "") + n + " -> " + Heresy(plr));
		}

		ActorBuffStackDef@ DivineFavorDef(PlayerBase@ plr)
		{
			string path = BindS(plr, DIVINE_FAVOR, "stacks-buff");
			return path.isEmpty() ? null : ActorBuffStackDef::Get(path);
		}

		bool PenanceReady(PlayerBase@ plr)
		{
			auto def = DivineFavorDef(plr);
			return def !is null && def.m_maxStacks > 0 && plr.GetStacks(def) >= def.m_maxStacks;
		}

		// the sum of the main hand's damage: the lunge's and the bloom's "weapon damage"
		float WeaponDamage(PlayerBase@ plr)
		{
			auto@ h = plr.m_record.currStats.MainHand;
			return h.DamagePhysical + h.DamageFire + h.DamageIce + h.DamageLightning + h.DamagePoison + h.DamagePure;
		}

		// --- bodies ---------------------------------------------------------------------------

		HWPSpecsBody@ BodyOf(UnitPtr u)
		{
			if (!Alive(u))
				return null;
			return cast<HWPSpecsBody>(u.GetScriptBehavior());
		}

		void PruneBodies()
		{
			for (int i = int(g_bodies.length()) - 1; i >= 0; i--)
			{
				auto b = g_bodies[i];
				if (b is null || !Alive(b.m_unit))
				{
					if (b !is null)
						b.m_glow = Kill(b.m_glow);
					g_bodies.removeAt(i);
				}
			}
		}

		// the body the cast takes: within RAISE_RANGE of the priest, the nearest to the aim line
		// (dir zero: the nearest to the priest)
		HWPSpecsBody@ PickBody(PlayerBase@ plr, vec2 dir)
		{
			PruneBodies();
			if (plr is null)
				return null;
			vec2 pos = xy(plr.m_unit.GetPosition());
			bool aimed = lengthsq(dir) > 0.01f;
			if (aimed)
				dir = normalize(dir);
			HWPSpecsBody@ best = null;
			float bestScore = 0;
			for (uint i = 0; i < g_bodies.length(); i++)
			{
				vec2 d = xy(g_bodies[i].m_unit.GetPosition()) - pos;
				float dst = length(d);
				if (dst > RAISE_RANGE)
					continue;
				float score = dst;
				if (aimed && dst > 1)
				{
					float along = dot(d, dir);
					float off = length(d - dir * along);
					// behind the aim counts as far away; ahead, the distance off the aim line
					score = along < 0 ? dst + RAISE_RANGE : off + dst * 0.25f;
				}
				if (best is null || score < bestScore)
				{
					@best = g_bodies[i];
					bestScore = score;
				}
			}
			return best;
		}

		// host: the roll on an enemy's death; chance from the Forgemaster on the floor with the
		// highest Call of Heresy (the local one when several)
		PlayerBase@ BestForgemaster()
		{
			PlayerBase@ best = null;
			float bestChance = -1;
			for (uint i = 0; i < g_players.length(); i++)
			{
				if (g_players[i].peer == 255 || g_players[i].actor is null)
					continue;
				auto p = cast<PlayerBase>(g_players[i].actor);
				if (p is null || !Learned(p, COH))
					continue;
				float c = BindF(p, COH, "coh-body", 0);
				if (c > bestChance || (c == bestChance && g_players[i].local))
				{
					@best = p;
					bestChance = c;
				}
			}
			return best;
		}

		UnitPtr SpawnBody(const string &in rel, vec2 pos)
		{
			auto prod = Resources::GetUnitProducer(BODIES_DIR + rel);
			if (prod is null)
			{
				LogError("specs", "no body unit for " + rel);
				return UnitPtr();
			}
			SpawnUnitBase sb;
			@sb.UnitType = prod;
			auto u = sb.SpawnUnit(pos, null, 1.0f);
			if (Alive(u))
			{
				g_bodiesSpawned++;
				Log("specs", "body " + rel + " at " + int(pos.x) + " " + int(pos.y) + " unit " + u.GetId());
			}
			return u;
		}

		void OnActorDestroyed(Actor@ a)
		{
			if (!Network::IsServer() || a is null || g_inTown)
				return;
			auto c = cast<CompositeActorBehavior>(a);
			if (c is null || !c.IsDead() || cast<IOwnedUnit>(a) !is null || a.Team == g_team_player)
				return;
			if (!a.m_unit.IsValid())
				return;
			string rel = RisenRel(a.m_unit.GetUnitProducer().GetResourceName());
			if (rel.isEmpty())
				return;
			auto fm = BestForgemaster();
			if (fm is null)
				return;
			g_bodyRolls++;
			float chance;
			if (HasActorTag(a, "boss"))
				chance = BindF(fm, COH, "dd-boss", 0);
			else
			{
				chance = BindF(fm, COH, "coh-body", 0);
				if (HasActorTag(a, "elite"))
					chance += BindF(fm, COH, "dd-elite", 0);
			}
			if (randf() >= chance)
				return;
			SpawnBody(rel, xy(a.m_unit.GetPosition()));
		}

		// a body is gone: the host destroys it (its existence is netsynced)
		void OnBodyGone(uint8 peer, SValue@ data)
		{
			auto u = g_scene.GetUnit(HWP::SV::Int(data, "body", 0));
			if (Alive(u) && cast<HWPSpecsBody>(u.GetScriptBehavior()) !is null)
				u.Destroy();
		}

		void RequestBodyGone(UnitPtr body)
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("body", body.GetId());
			b.PopDictionary();
			HWP::Net::Request("specs.body_gone", b.Build());
		}

		// host: raise the body for the requesting peer's player
		void OnRaise(uint8 peer, SValue@ data)
		{
			auto u = g_scene.GetUnit(HWP::SV::Int(data, "body", 0));
			auto body = BodyOf(u);
			int bodyId = HWP::SV::Int(data, "body", 0);
			if (body is null)
			{
				// another Forgemaster's raise got there first, or the body's time ran out
				Log("specs", "raise: body " + bodyId + " is gone, denied for peer " + peer);
				RaiseAnswer(peer, "specs.raise_denied", bodyId, 0);
				return;
			}
			auto rec = GetPlayerRecordByPeer(peer);
			if (rec is null || rec.actor is null)
				return;
			auto prod = Resources::GetUnitProducer(body.m_source);
			if (prod is null)
			{
				LogError("specs", "raise: no risen unit " + body.m_source);
				RaiseAnswer(peer, "specs.raise_denied", bodyId, 0);
				return;
			}
			vec2 pos = xy(u.GetPosition());
			SpawnUnitBase sb;
			@sb.UnitType = prod;
			sb.WeaponInfo = NR;
			auto risen = sb.SpawnUnit(pos, rec.actor, 1.0f);
			u.Destroy();
			g_raises++;
			g_lastRaise = body.m_source.substr(RISEN_DIR.length());
			Log("specs", "raised " + g_lastRaise + " for peer " + peer + " unit " + (Alive(risen) ? risen.GetId() : -1)
				+ (body.m_boss ? " boss" : body.m_elite ? " elite" : ""));
			RaiseAnswer(peer, "specs.raised", bodyId, body.m_boss ? 3 : body.m_elite ? 2 : 1);
		}

		void RaiseAnswer(uint8 peer, const string &in name, int bodyId, int heresy)
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("body", bodyId);
			b.PushInteger("heresy", heresy);
			b.PopDictionary();
			HWP::Net::Send(peer, name, b.Build());
		}

		// the caster's client: the host raised the body, Heresy +1 (+2 elite, +3 boss)
		void OnRaised(SValue@ data)
		{
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			if (plr !is null)
				AddHeresy(plr, HWP::SV::Int(data, "heresy", 1));
		}

		// the caster's client: no body to raise when the host looked: no Heresy, and the cooldown
		// the completed channel started is given back
		void OnRaiseDenied(SValue@ data)
		{
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			if (plr is null)
				return;
			auto sk = FindSkill(plr, NR);
			if (sk !is null)
				sk.ResetCooldown();
			Log("specs", "raise denied: body " + HWP::SV::Int(data, "body", 0) + " was gone");
		}

		// --- the channel (the caster's client) -------------------------------------------------

		void StartChannel(PlayerBase@ plr, HWPSpecsBody@ body, bool penance, int duration = -1,
			HWPSpecsResurrection@ skill = null, PointCost@ cost = null)
		{
			if (plr is null || body is null)
				return;
			if (duration < 0)
				duration = penance ? CHANNEL_NORMAL : body.m_boss ? CHANNEL_BOSS : body.m_elite ? CHANNEL_ELITE : CHANNEL_NORMAL;
			auto c = RaiseChannel();
			@c.m_plr = plr;
			c.m_body = body.m_unit;
			c.m_penance = penance;
			c.m_left = duration;
			c.m_total = duration;
			@c.m_skill = skill;
			@c.m_cost = cost;
			c.m_dodge = penance && duration > 0;
			c.m_spot = EatSpot(body.m_unit);
			c.m_label = penance ? "Penance" : "Raising";
			@g_channel = c;
			g_chanPulses = 0;
			g_chanDashRefused = 0;
			g_chanLockFacing = 999;
			g_chanBeamFrames = 0;
			if (duration > 0)
				Give(plr, plr, Buff("raising"), 1.0f, duration);
			if (c.m_dodge)
				Give(plr, plr, Buff("penance_stance"), 1.0f, duration);
			// a raise locks onto the body at once: facing it, the dash pinned, the beam on; a Penance
			// does the same once its dodge has landed (UpdatePenanceStance -> LockOn)
			if (!penance && duration > 0)
			{
				vec2 d = xy(body.m_unit.GetPosition()) - xy(plr.m_unit.GetPosition());
				LockOn(c, length(d) > 0.5f ? atan(d.y, d.x) : plr.m_dirAngle);
			}
			Log("specs", (penance ? "penance" : "raise") + " channel " + duration + " ms on " + body.m_unit.GetId());
		}

		// the channel's lock: the facing held (the raising buff's lock-rotation keeps SetAngle's
		// value, Player.as aimDir), the dash pinned, the beam started
		void LockOn(RaiseChannel@ c, float angle)
		{
			if (c.m_locked)
				return;
			c.m_locked = true;
			c.m_angle = angle;
			c.m_plr.SetAngle(angle);
			PinDash(c);
			StartBeam(c);
			Log("specs", "channel locked on " + c.m_body.GetId() + " facing " + Rounded(angle * 180 / PI));
		}

		// the Dash has ignore-blocking (dash.sval), so the raising buff's silence never stops it:
		// its cooldown is kept past the channel's end instead (ActiveSkill.Activate refuses on
		// m_cooldownC > 0), and let go when the channel ends (UnpinDash)
		void PinDash(RaiseChannel@ c)
		{
			auto dash = cast<Skills::Charge>(FindSkill(c.m_plr, DASH));
			if (dash is null)
				return;
			if (c.m_dashReal < 0)
			{
				c.m_dashReal = max(0, dash.m_cooldownC);
				c.m_dashPinLeft = c.m_left;
			}
			int want = c.m_left + DASH_PIN_MS;
			if (dash.m_cooldownC < want)
				dash.m_cooldownC = want;
			g_dashPinned = true;
		}

		void UnpinDash(RaiseChannel@ c)
		{
			if (!g_dashPinned)
				return;
			g_dashPinned = false;
			if (c is null || c.m_plr is null)
				return;
			auto dash = cast<Skills::Charge>(FindSkill(c.m_plr, DASH));
			// still the pin's cooldown: back to what is left of the dash's own (a dash just
			// before the channel keeps its cooldown when the channel is cut short)
			if (dash !is null && dash.m_cooldownC > 0 && dash.m_cooldownC <= c.m_left + DASH_PIN_MS)
			{
				int real = c.m_dashReal < 0 ? 0 : max(0, c.m_dashReal - (c.m_dashPinLeft - c.m_left));
				dash.m_cooldownC = real;
			}
			c.m_dashReal = -1;
		}

		// the beam: a raise's runs from the priest to the body in necrotic green; a Penance's rises
		// straight up out of the body in gold (the priest stands under it)
		void StartBeam(RaiseChannel@ c)
		{
			if (c.m_beam.IsValid())
				return;
			if (c.m_penance)
			{
				vec2 at = xy(c.m_body.GetPosition());
				dictionary ps = { { 'angle', -PI / 2 }, { 'length', 24.0f }, { 'width', 2.0f }, { 'cR', 1.6f }, { 'cG', 1.2f }, { 'cB', 0.3f } };
				c.m_beam = Loop(BEAM, at, ps);
				return;
			}
			vec2 from = xy(c.m_plr.m_unit.GetPosition());
			vec2 to = xy(c.m_body.GetPosition());
			dictionary ps = { { 'angle', atan(to.y - from.y, to.x - from.x) }, { 'length', max(8.0f, dist(from, to)) }, { 'width', 2.0f },
				{ 'cR', 0.4f }, { 'cG', 1.6f }, { 'cB', 0.5f } };
			c.m_beam = Loop(BEAM, from, ps);
		}

		// each frame: the beam widens (a Penance's also rises) with the progress, the body pulses
		void UpdateChannelFx(RaiseChannel@ c, int ms)
		{
			if (!c.m_locked)
				return;
			float t = c.Progress();
			if (c.m_beam.IsValid() && !c.m_beam.IsDestroyed())
			{
				auto eb = cast<EffectBehavior>(c.m_beam.GetScriptBehavior());
				if (eb !is null)
				{
					eb.SetParam("width", 2.0f + 14.0f * t);
					if (c.m_penance)
						eb.SetParam("length", 24.0f + 110.0f * t);
					g_chanBeamFrames++;
				}
			}
			if (c.m_penance)
				return;   // UpdatePenanceStance pulses the golden light
			c.m_pulseC -= ms;
			if (c.m_pulseC <= 0)
			{
				c.m_pulseC += CHANNEL_PULSE_MS;
				dictionary ps = { { 'scale', 0.4f + 2.0f * t } };
				PlayEffect(FX + "channel_pulse.effect", xy(c.m_body.GetPosition()), ps);
				c.m_pulses++;
				g_chanPulses = c.m_pulses;
				g_chanLockFacing = Rounded(c.m_plr.m_dirAngle * 180 / PI);
			}
		}

		void EndChannelFx(RaiseChannel@ c)
		{
			if (c is null)
				return;
			c.m_beam = Kill(c.m_beam);
			UnpinDash(c);
			g_chanDashRefused = c.m_dashRefused;
		}

		void CancelChannel(const string &in why)
		{
			if (g_channel is null)
				return;
			Log("specs", "channel cancelled: " + why);
			EndChannelFx(g_channel);
			@g_channel = null;
		}

		void CompleteChannel()
		{
			auto c = g_channel;
			@g_channel = null;
			if (c is null)
				return;
			EndChannelFx(c);
			auto body = BodyOf(c.m_body);
			auto plr = c.m_plr;
			if (body is null || plr is null || plr.IsDead())
				return;
			// the skill's cost and cooldown, now that the channel has run its course
			if (c.m_cost !is null)
				plr.UsePoints(true, true, c.m_cost);
			if (!c.m_penance && c.m_skill !is null)
				c.m_skill.StartRaiseCooldown();
			if (c.m_penance)
			{
				int rm = BindI(plr, NR, "nr-penance", 1) + (body.m_elite ? 1 : 0) + (body.m_boss ? 2 : 0);
				AddHeresy(plr, -min(rm, Heresy(plr)));
				auto df = DivineFavorDef(plr);
				if (df !is null)
					plr.AddStacks(plr, df, -999);
				auto sk = FindSkill(plr, NR);
				if (sk !is null)
					sk.ResetCooldown();
				g_penances++;
				Log("specs", "penance removed " + rm + " heresy");
				RequestBodyGone(c.m_body);
			}
			else
			{
				// Heresy comes with the host's answer (OnRaised / OnRaiseDenied)
				SValueBuilder b;
				b.PushDictionary();
				b.PushInteger("body", c.m_body.GetId());
				b.PopDictionary();
				HWP::Net::Request("specs.raise", b.Build());
			}
		}

		void UpdateChannel(int ms)
		{
			if (g_channel is null)
				return;
			auto c = g_channel;
			if (c.m_plr is null || c.m_plr.IsDead())
			{
				CancelChannel("the priest died");
				return;
			}
			if (BodyOf(c.m_body) is null)
			{
				CancelChannel("the body is gone");
				return;
			}
			auto raising = Buff("raising");
			if (c.m_total > 0 && raising !is null && !c.m_plr.HasBuff(raising.m_pathHash))
			{
				CancelChannel("the raising buff ended early");
				return;
			}
			if (c.m_penance && c.m_total > 0)
				UpdatePenanceStance(c, ms);
			if (c.m_locked)
			{
				// the lock holds: the facing (a frame can slip before the buff's lock-rotation lands),
				// the dash's cooldown (a dash charge gained mid-channel resets nothing here)
				if (abs(c.m_plr.m_dirAngle - c.m_angle) > 0.01f)
					c.m_plr.SetAngle(c.m_angle);
				PinDash(c);
			}
			UpdateChannelFx(c, ms);
			c.m_left -= ms;
			if (c.m_left <= 0)
				CompleteChannel();
		}

		// a dash press while the channel holds the dash: refused (the pinned cooldown), counted, logged
		void OnDashPressed()
		{
			if (g_channel is null || !g_channel.m_locked)
				return;
			g_channel.m_dashRefused++;
			g_chanDashRefused = g_channel.m_dashRefused;
			Log("specs", "dash refused during " + (g_channel.m_penance ? "penance" : "raise") + " channel, " + g_channel.m_left + " ms left");
		}

		// the channel bar over the priest's head: the label, the progress, gold for a Penance and
		// necrotic green for a raise. Drawn by HWPSpecsModule.RenderFrame (the UI-scaled batch, so
		// world -> screen is ToScreenspace / m_wndScale, as FloatingText.as does).
		BitmapString@ g_barText;
		string g_barTextFor;

		void RenderForgemaster(int idt, SpriteBatch& sb)
		{
			auto c = g_channel;
			if (c is null || c.m_plr is null || !IsLocal(c.m_plr) || c.m_total <= 0)
			{
				g_chanDrawn = false;
				return;
			}
			if (g_barText is null || g_barTextFor != c.m_label)
			{
				auto font = Resources::GetBitmapFont("gui/fonts/arial11.fnt");
				@g_barText = font.BuildText(c.m_label, -1, TextAlignment::Center, vec4(1, 1, 1, 1));
				g_barTextFor = c.m_label;
			}
			vec2 at = ToScreenspace(c.m_plr.m_unit.GetInterpolatedPosition(idt) + vec3(0, -BAR_ABOVE, 0)) / g_gameMode.m_wndScale;
			at = vec2(int(at.x - BAR_W / 2), int(at.y));
			float t = c.Progress();
			vec4 fill = c.m_penance ? vec4(1.0f, 0.85f, 0.3f, 1) : vec4(0.45f, 1.0f, 0.5f, 1);
			sb.FillRectangle(vec4(at.x - 1, at.y - 1, BAR_W + 2, BAR_H + 2), vec4(0, 0, 0, 0.75f));
			sb.FillRectangle(vec4(at.x, at.y, int(BAR_W * t), BAR_H), fill);
			if (g_barText !is null)
				sb.DrawString(vec2(int(at.x + BAR_W / 2), int(at.y - g_barText.GetHeight() - 1)), g_barText);
			g_chanDrawn = true;
		}

		// the Penance stance: the first frame dodges to under the body (not from inside the skill's
		// own NetActivate), the landing faces up, and the body shines gold, brighter as the channel runs
		void UpdatePenanceStance(RaiseChannel@ c, int ms)
		{
			auto plr = c.m_plr;
			if (c.m_dodge)
			{
				c.m_dodge = false;
				c.m_dodging = DodgeTo(plr, c.m_spot);
				c.m_dodgeC = DODGE_MAX_MS;
				if (!c.m_dodging)
					FaceUp(plr);
			}
			if (c.m_dodging)
			{
				c.m_dodgeC -= ms;
				if (DodgeDone(plr) || c.m_dodgeC <= 0)
				{
					c.m_dodging = false;
					Land(plr, c.m_spot);
				}
			}
			if (!c.m_dodging && !c.m_locked)
				LockOn(c, -PI / 2);   // landed: facing up, the dash pinned, the golden beam out of the body
			c.m_lightC -= ms;
			if (c.m_lightC <= 0)
			{
				c.m_lightC += PEN_LIGHT_MS;
				float t = 1.0f - float(c.m_left) / float(max(1, c.m_total));   // 0 at the start, 1 at the end
				dictionary ps = { { 'scale', 0.4f + 2.0f * t } };
				c.m_pulses++;
				g_chanPulses = c.m_pulses;
				vec2 at = xy(c.m_body.GetPosition());
				PlayEffect(FX + "penance_light.effect", at, ps);
				g_penLights++;
				if (!c.m_dodging)
				{
					vec2 pp = xy(plr.m_unit.GetPosition());
					g_penFacing = Rounded(plr.m_dirAngle * 180 / PI);
					g_penBeside = Rounded(pp.x - at.x);
					g_penUnder = Rounded(pp.y - at.y);
				}
			}
		}

		// --- the dodge to a body, shared by the lunge and the Penance -----------------------------

		vec2 EatSpot(UnitPtr body)
		{
			vec2 p = xy(body.GetPosition());
			return vec2(p.x, p.y + EAT_BELOW);
		}

		// the player's own Dash (Skills::Charge) for exactly the distance to the spot: the dodge
		// animation, dust and sound, seen by every peer (Activate sends PlayerActiveSkillActivate).
		// False, and the priest is put on the spot, when the dash can't go (no dash charge).
		bool DodgeTo(PlayerBase@ plr, vec2 spot)
		{
			vec2 from = xy(plr.m_unit.GetPosition());
			vec2 d = spot - from;
			float len = length(d);
			if (len >= 2)
			{
				auto dash = cast<Skills::Charge>(FindSkill(plr, DASH));
				if (dash !is null)
				{
					// the dash's castpoint is 0, which Activate makes 1 ms: NetDoActivate copies m_dist into
					// m_distC on the next frame, so the shortened m_dist stays until the landing restores it
					// (eat 20261022-152706: restored at once, the dash ran its full 90 px after the snap)
					if (g_dashKeep < 0)
						g_dashKeep = dash.m_dist;
					dash.m_dist = int(len + 0.5f);
					dash.ResetCooldown();
					if (dash.Activate(d / len, 1.0f))
						return true;
					RestoreDash(dash);
				}
			}
			auto p = plr.m_unit.GetPosition();
			plr.m_unit.SetPosition(spot.x, spot.y, p.z);
			return false;
		}

		int g_dashKeep = -1;   // the dash's own m_dist while a dodge borrows it

		void RestoreDash(Skills::Charge@ dash)
		{
			if (dash !is null && g_dashKeep >= 0)
				dash.m_dist = g_dashKeep;
			g_dashKeep = -1;
		}

		int Rounded(float v) { return int(v + (v < 0 ? -0.5f : 0.5f)); }

		bool DodgeDone(PlayerBase@ plr)
		{
			auto dash = cast<Skills::Charge>(FindSkill(plr, DASH));
			// not before the cast fired (m_castingC, 1 ms) and the distance is used up
			return dash is null || (dash.m_castingC <= 0 && dash.m_distC <= 0);
		}

		// facing the body: up the screen (-y); the devouring and penance_stance buffs lock the rotation
		void FaceUp(PlayerBase@ plr)
		{
			plr.SetAngle(-PI / 2);
		}

		void Land(PlayerBase@ plr, vec2 spot)
		{
			auto dash = cast<Skills::Charge>(FindSkill(plr, DASH));
			if (dash !is null && dash.m_distC > 0)
				dash.CancelCharge();   // the 600 ms fallback: a dash still running would carry on past the spot
			RestoreDash(dash);
			auto p = plr.m_unit.GetPosition();
			plr.m_unit.SetPosition(spot.x, spot.y, p.z);
			FaceUp(plr);
		}

		// the eating: the landing, then the bob and the blood until the devouring buff ends or the
		// body is gone (another Forgemaster's raise, its time up); the body goes when the eating ends
		void UpdateEating(int ms)
		{
			if (g_eat is null)
				return;
			auto e = g_eat;
			auto plr = e.m_plr;
			if (plr is null || plr.IsDead())
			{
				@g_eat = null;
				return;
			}
			if (e.m_dodging)
			{
				e.m_dodgeC -= ms;
				if (!DodgeDone(plr) && e.m_dodgeC > 0)
					return;
				e.m_dodging = false;
				Land(plr, e.m_spot);
			}
			auto dv = Buff("devouring");
			if (dv is null || !plr.HasBuff(dv.m_pathHash) || !Alive(e.m_body))
			{
				if (Alive(e.m_body))
					RequestBodyGone(e.m_body);
				Log("specs", "eaten: " + e.m_bobs + " bobs, " + e.m_bloods + " bloods");
				g_eatBobs = e.m_bobs;
				g_eatBloods = e.m_bloods;
				@g_eat = null;
				return;
			}
			e.m_bobC -= ms;
			if (e.m_bobC <= 0)
			{
				e.m_bobC += EAT_BOB_MS;
				e.m_up = !e.m_up;
				e.m_bobs++;
				g_eatFacing = Rounded(plr.m_dirAngle * 180 / PI);
				auto p = plr.m_unit.GetPosition();
				plr.m_unit.SetPosition(e.m_spot.x, e.m_spot.y - (e.m_up ? 1 : 0), p.z);
			}
			e.m_bloodC -= ms;
			if (e.m_bloodC <= 0)
			{
				e.m_bloodC += EAT_BLOOD_MS;
				e.m_bloods++;
				dictionary ps = { { 'scale', 0.8f } };
				PlayEffect("effects/gore/blood/hit_blood.effect", xy(e.m_body.GetPosition()), ps);
			}
		}

		// --- the lunge (the Forgemaster's client) ----------------------------------------------

		void Lunge(PlayerBase@ plr, HWPSpecsBody@ body)
		{
			vec2 pos = xy(body.m_unit.GetPosition());
			Give(plr, plr, Buff("devouring"), 1.0f, -1);
			auto e = Eating();
			@e.m_plr = plr;
			e.m_body = body.m_unit;
			e.m_spot = EatSpot(body.m_unit);
			e.m_dodging = DodgeTo(plr, e.m_spot);
			e.m_dodgeC = DODGE_MAX_MS;
			e.m_bobC = EAT_BOB_MS;
			if (!e.m_dodging)
				FaceUp(plr);
			@g_eat = e;
			float rl = BindF(plr, COH, "rl-dmg", 0);
			if (rl > 0)
			{
				bool knock = BindI(plr, COH, "rl-knock", 0) > 0;
				auto enemies = EnemiesNear(pos, LUNGE_HIT_RADIUS, g_team_player);
				for (uint i = 0; i < enemies.length(); i++)
				{
					auto e = enemies[i];
					if (!FilterHuskDamage(plr, e.m_unit, false))
						continue;
					vec2 d = xy(e.m_unit.GetPosition()) - pos;
					vec2 dir = lengthsq(d) > 0.01f ? normalize(d) : vec2(1, 0);
					DamageInfo di(plr, COH);
					di.PhysicalDamage = uint32(rl * WeaponDamage(plr));
					e.Damage(di, xy(e.m_unit.GetPosition()), dir);
					if (knock && !e.IsDead())
						e.m_unit.GetPhysicsBody().SetLinearVelocity(dir * 180.0f);
				}
			}
			g_lunges++;
			Log("specs", "lunge at " + body.m_unit.GetId() + (rl > 0 ? " hitting for " + int(rl * WeaponDamage(plr)) : ""));
		}

		// The roll is the Forgemaster's own client's, like the channel (its position and buffs are
		// its client's to set, and the hit's damage goes through the summon damage path). Two
		// Forgemasters can each lunge the same body: the host destroys it once (OnBodyGone) and
		// both get their devouring buff, which is harmless.
		void UpdateLunge(PlayerBase@ plr)
		{
			if (plr is null || plr.IsDead() || g_channel !is null || g_eat !is null)
				return;
			int heresy = Heresy(plr);
			float per = BindF(plr, COH, "coh-lunge", 0);
			vec2 pos = xy(plr.m_unit.GetPosition());
			for (uint i = 0; i < g_bodies.length(); i++)
			{
				auto b = g_bodies[i];
				if (b.m_rolled || distsq(xy(b.m_unit.GetPosition()), pos) > LUNGE_RANGE * LUNGE_RANGE)
					continue;
				b.m_rolled = true;
				float chance = heresy * per;
				Log("specs", "lunge roll on " + b.m_unit.GetId() + " chance " + int(chance * 100 + 0.5f) + "%");
				if (chance > 0 && randf() < chance)
				{
					Lunge(plr, b);
					return;
				}
			}
		}

		// --- bodies' upkeep ----------------------------------------------------------------------

		void UpdateBodies(int ms, PlayerBase@ forgemaster)
		{
			PruneBodies();
			for (uint i = 0; i < g_bodies.length(); i++)
			{
				auto b = g_bodies[i];
				if (Network::IsServer())
				{
					b.m_ttl -= ms;
					if (b.m_ttl <= 0)
					{
						b.m_unit.Destroy();
						continue;
					}
				}
				if (forgemaster !is null)
				{
					if (!b.m_glow.IsValid() || b.m_glow.IsDestroyed())
						b.m_glow = Loop(FX + "body_glow.effect", xy(b.m_unit.GetPosition()));
				}
				else if (b.m_glow.IsValid())
					b.m_glow = Kill(b.m_glow);
			}
		}

		// --- the risen ----------------------------------------------------------------------------

		string AnimToString(AnimString@ a)
		{
			if (a is null)
				return "idle";
			if (a.m_numDirs <= 0)
				return a.m_anim;
			return a.m_anim.substr(0, a.m_anim.length() - 1) + " " + a.m_numDirs;
		}

		// a follower movement in the old one's image, or null when the old one is kept
		ActorMovement@ FollowerFor(UnitPtr unit, CompositeActorBehavior@ b, ActorMovement@ old)
		{
			if (old is null || cast<MeleeFollowerMovement>(old) !is null || cast<RangedFollowerMovement>(old) !is null)
				return null;
			auto mm = cast<MeleeMovement>(old);
			if (mm is null)
				return null;
			bool ranged = cast<RangedMovement>(old) !is null;
			SValueBuilder sb;
			sb.PushDictionary();
			sb.PushString("anim-idle", AnimToString(mm.m_idleAnim));
			sb.PushString("anim-walk", AnimToString(mm.m_walkAnim));
			sb.PushFloat("speed", max(2.0f, mm.m_speed));
			sb.PushFloat("run-back-speed", max(6.0f, mm.m_speed * 1.4f));
			sb.PushInteger("run-back-distance", 180);
			sb.PushInteger("dist", mm.m_standDist);
			sb.PushFloat("roaming", 0.5f);
			sb.PushInteger("roaming-distance", 60);
			sb.PushBoolean("flying", mm.m_flying);
			sb.PopDictionary();
			SValue@ sv = sb.Build();
			ActorMovement@ nm;
			if (ranged)
				@nm = RangedFollowerMovement(unit, sv);
			else
				@nm = MeleeFollowerMovement(unit, sv);
			nm.Initialize(unit, b);
			g_movesSwapped++;
			return nm;
		}

		bool DangerousSpawn(SpawnUnit@ su)
		{
			if (su is null)
				return false;
			if (su.UnitType !is null && IsEnemyUnit(su.UnitType.GetResourceName()))
				return true;
			for (uint i = 0; i < su.m_unitEntries.length(); i++)
			{
				if (su.m_unitEntries[i].m_prod !is null && IsEnemyUnit(su.m_unitEntries[i].m_prod.GetResourceName()))
					return true;
			}
			return false;
		}

		// the effects a fight's script runs through its actors' skills (an effect in an action
		// list sits in an ActionEffectWrapper). SetFlag stays: a boss's phase flags are level
		// flags its own skills read (CondFlag), and the floor's script is done with them once the
		// boss has died. TargetRandomPlayer goes: on a summon it would aim the boss at its owner.
		bool DangerousEffect(IEffect@ e)
		{
			if (e is null)
				return false;
			if (cast<RaiseGlobalEvent>(e) !is null || cast<RaiseGlobalEventRanged>(e) !is null || cast<SeekPointOfInterest>(e) !is null
				|| cast<SetPointOfInterest>(e) !is null || cast<GiveShadowCurse>(e) !is null || cast<TargetRandomPlayer>(e) !is null
				|| cast<BoxAnnounce>(e) !is null || cast<GiveMaterial>(e) !is null)
				return true;
			return DangerousSpawn(cast<SpawnUnit>(e));
		}

		bool Dangerous(IAction@ a)
		{
			if (a is null)
				return false;
			if (cast<RaiseGlobalEvent>(a) !is null || cast<RaiseGlobalEventRanged>(a) !is null || cast<RaiseUnitEvent>(a) !is null
				|| cast<SeekPointOfInterest>(a) !is null)
				return true;
			auto w = cast<ActionEffectWrapper>(a);
			if (w !is null)
				return DangerousEffect(w.m_effect);
			return DangerousSpawn(cast<SpawnUnit>(a));
		}

		void StripList(ActionList@ list)
		{
			if (list is null)
				return;
			for (int i = int(list.m_actions.length()) - 1; i >= 0; i--)
			{
				if (Dangerous(list.m_actions[i].m_action))
				{
					list.m_actions.removeAt(i);
					g_actionsStripped++;
				}
			}
		}

		void StripSkill(ACompositeActorSkill@ s)
		{
			if (s is null)
				return;
			auto cs = cast<CompositeActorSkill>(s);
			if (cs !is null)
				StripList(cs.m_actions);
			auto act = cast<CompositeActorActiveSkill>(s);
			if (act !is null)
			{
				StripList(act.m_startActions);
				StripList(act.m_stopActions);
			}
			auto tr = cast<CompositeActorTriggeredSkill>(s);
			if (tr !is null)
				StripList(tr.m_actions);
			auto ut = cast<CompositeActorUtilitySkill>(s);
			if (ut !is null)
				StripList(ut.m_actions);
			auto ch = cast<ChannelingBaseSkill>(s);
			if (ch !is null)
				StripList(ch.m_actions);
			auto ds = cast<DashStrike>(s);
			if (ds !is null)
				StripList(ds.m_actions);
			auto bs = cast<BlinkStrikeSkill>(s);
			if (bs !is null)
				StripList(bs.m_actions);
			auto bw = cast<BeamSkillSweep>(s);
			if (bw !is null)
				StripList(bw.m_actions);
		}

		void StripSkills(array<ACompositeActorSkill@>@ skills)
		{
			if (skills is null)
				return;
			for (uint i = 0; i < skills.length(); i++)
				StripSkill(skills[i]);
		}

		// the owner's binds for a risen; the defaults are level 1's
		float RisenBind(PlayerBase@ plr, const string &in name, float def)
		{
			return plr is null ? def : BindF(plr, NR, name, def);
		}

		uint RisenSeq(IOwnedUnit@ u)
		{
			auto r = cast<HWPSpecsRisen>(u);
			if (r !is null)
				return r.m_seq;
			auto s = cast<HWPSpecsRisenState>(u);
			if (s !is null)
				return s.m_seq;
			return 0;
		}

		// the owner's client keeps the total at nr-count: the oldest die first (Player.as's way)
		void EnforceCap(PlayerBase@ plr)
		{
			if (plr is null || !Learned(plr, NR))
				return;
			int cap = BindI(plr, NR, "nr-count", 2);
			auto risen = RisenUnits(plr);
			while (int(risen.length()) > cap)
			{
				uint oldest = 0;
				for (uint i = 1; i < risen.length(); i++)
				{
					if (RisenSeq(risen[i]) < RisenSeq(risen[oldest]))
						oldest = i;
				}
				DestroyRisen(risen[oldest]);
				risen.removeAt(oldest);
				g_capKills++;
				Log("specs", "cap " + cap + ": the oldest risen is gone");
			}
		}

		// the player's living risen: the summons of the risen producers (RISEN_DIR)
		array<IOwnedUnit@> RisenUnits(PlayerBase@ plr)
		{
			array<IOwnedUnit@> risen;
			if (plr is null || plr.m_record is null)
				return risen;
			auto@ summons = plr.m_record.summons;
			for (uint i = 0; i < summons.length(); i++)
			{
				if (summons[i].m_prod is null || summons[i].m_prod.GetResourceName().findFirst(RISEN_DIR) != 0)
					continue;
				for (uint j = 0; j < summons[i].m_units.length(); j++)
				{
					auto u = summons[i].m_units[j];
					if (u !is null && Alive(u.GetUnit()))
						risen.insertLast(u);
				}
			}
			return risen;
		}

		// a risen's end, from any peer (a client asks the host, as Player.as does for its summons)
		void DestroyRisen(IOwnedUnit@ u)
		{
			if (Network::IsServer())
				u.Destroy();
			else
				(Network::Message("UnitDestroyed") << u.GetUnit()).SendToHost();
		}

		int RisenCount(PlayerBase@ plr)
		{
			if (plr is null)
				return 0;
			int n = 0;
			auto@ summons = plr.m_record.summons;
			for (uint i = 0; i < summons.length(); i++)
			{
				if (summons[i].m_prod is null || summons[i].m_prod.GetResourceName().findFirst(RISEN_DIR) != 0)
					continue;
				for (uint j = 0; j < summons[i].m_units.length(); j++)
				{
					if (summons[i].m_units[j] !is null && Alive(summons[i].m_units[j].GetUnit()))
						n++;
				}
			}
			return n;
		}

		// --- the free Divine Favor and the Heresy HUD ------------------------------------------------

		void OnPlayerInitialize(PlayerBase@ plr)
		{
			if (plr is null || plr.m_record is null || !plr.m_record.local || !Learned(plr, COH))
				return;
			auto rec = plr.m_record;
			auto bag = HWP::SaveData::Player(rec);
			if (bag.GetBool("fm_free_favor", false))
				return;
			auto def = rec.playerClass.GetSkillDef(DIVINE_FAVOR);
			if (def is null)
				return;
			int lvl = 0;
			if (!rec.pickedSkills.get("divine_favor", lvl))
				lvl = 0;
			int cost = def.m_levelSkillCost.length() > uint(def.m_startingLevel) ? def.m_levelSkillCost[def.m_startingLevel] : 0;
			bag.SetBool("fm_free_favor", true);
			rec.bonusSkillPts += cost;
			if (lvl <= 0)
			{
				rec.pickedSkills.set("divine_favor", 1);
				(Network::Message("PlayerSyncSkillLevel") << def.m_idHash << 1 << false).SendToAll();
			}
			rec.SyncStatPoints();
			rec.SyncTownStatPoints();
			plr.LoadSkills();
			rec.RefreshModifiers();
			Log("specs", "forgemaster: Divine Favor level 1 for free (" + cost + " point(s) back)");
		}

		void UpdateHeresyHud(PlayerBase@ plr)
		{
			auto def = Stack(HERESY);
			if (def is null || def.m_buffDef is null)
				return;
			if (g_hudHeresy is null)
			{
				@g_hudHeresy = def.m_buffDef.m_hud;
				@g_hudHeresy5 = ScriptSprite(Resources::GetTexture2D("players/hwp/specs/icons.png"), vec4(208, 144, 14, 14));
			}
			bool high = Heresy(plr) >= HERESY_BLOCK;
			if (high != g_hudHeresyHigh)
			{
				g_hudHeresyHigh = high;
				@def.m_buffDef.m_hud = high ? g_hudHeresy5 : g_hudHeresy;
			}
		}

		void UpdateForgemaster(int ms, bool dashPressed = false)
		{
			auto fm = LocalForgemaster();
			if (dashPressed)
				OnDashPressed();
			UpdateBodies(ms, fm);
			if (fm is null)
			{
				if (g_channel !is null)
					CancelChannel("no forgemaster");
				return;
			}
			if (g_inTown)
			{
				if (Heresy(fm) > 0)
					AddHeresy(fm, -Heresy(fm));
				return;
			}
			UpdateChannel(ms);
			UpdateEating(ms);
			UpdateLunge(fm);
			UpdateHeresyHud(fm);
			auto sk = cast<HWPSpecsResurrection>(FindSkill(fm, NR));
			if (sk !is null)
				sk.RefreshIcon(PenanceReady(fm));
			g_capC -= ms;
			if (g_capC <= 0)
			{
				g_capC = 500;
				EnforceCap(fm);
			}
		}

		// --- `hwp forge` ----------------------------------------------------------------------------

		string MoveName(ActorMovement@ m)
		{
			if (m is null) return "none";
			if (cast<RangedFollowerMovement>(m) !is null) return "RangedFollower";
			if (cast<MeleeFollowerMovement>(m) !is null) return "MeleeFollower";
			if (cast<RangedMovement>(m) !is null) return "Ranged";
			if (cast<CirclingMovement>(m) !is null) return "Circling";
			if (cast<FleeMovement>(m) !is null) return "Flee";
			if (cast<PatrolMovement>(m) !is null) return "Patrol";
			if (cast<MeleeMovement>(m) !is null) return "Melee";
			if (cast<ChargeMovement>(m) !is null) return "Charge";
			if (cast<PassiveMovement>(m) !is null) return "Passive";
			if (cast<BossWormMovement>(m) !is null) return "BossWorm";
			return "other";
		}

		string RisenLine(IOwnedUnit@ u, PlayerBase@ plr)
		{
			auto a = cast<CompositeActorBehavior>(u);
			if (a is null)
				return "?";
			string name = a.m_unit.GetUnitProducer().GetResourceName();
			if (name.findFirst(RISEN_DIR) == 0)
				name = name.substr(RISEN_DIR.length());
			string mv = MoveName(a.m_movement);
			auto p = a.m_unit.GetPosition();
			return name + " id " + a.m_unit.GetId() + " hp " + int(float(a.m_hp) * 1000 + 0.5f) + " max " + a.GetMaxHp()
				+ " at " + int(p.x) + " " + int(p.y) + " dist " + int(dist(xy(p), xy(plr.m_unit.GetPosition())))
				+ " move " + mv + " target " + (a.m_target is null ? "none" : "" + a.m_target.m_unit.GetId())
				+ " dead " + (a.IsDead() ? 1 : 0);
		}

		void CmdForge(array<string>@ args)
		{
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			if (plr is null)
			{
				HWP::Commands::Reply("forge: no player");
				return;
			}
			string sub = args.length() > 0 ? args[0] : "";
			vec2 pos = xy(plr.m_unit.GetPosition());
			if (sub == "body" && args.length() >= 2)
			{
				// hwp forge body <rel under actors/> [dx dy]: the host drops that enemy's intact body
				if (!Network::IsServer())
				{
					HWP::Commands::Reply("forge: bodies are the host's");
					return;
				}
				string rel = args[1];
				if (RisenRel("actors/" + rel).isEmpty())
				{
					HWP::Commands::Reply("forge: not raisable: " + rel);
					return;
				}
				vec2 off(40, 0);
				if (args.length() > 3)
					off = vec2(float(parseFloat(args[2])), float(parseFloat(args[3])));
				auto u = SpawnBody(rel, pos + off);
				HWP::Commands::Reply("forge: body " + rel + " unit " + (Alive(u) ? u.GetId() : -1));
				return;
			}
			if (sub == "raise" || sub == "penance")
			{
				// hwp forge raise|penance [now]: the channel on the nearest body ("now": done at once)
				auto body = PickBody(plr, vec2(0, 0));
				if (body is null)
				{
					HWP::Commands::Reply("forge: no body within " + RAISE_RANGE);
					return;
				}
				bool now = args.length() > 1 && args[1] == "now";
				StartChannel(plr, body, sub == "penance", now ? 0 : -1);
				if (now)
					CompleteChannel();
				HWP::Commands::Reply("forge: " + sub + (now ? " done" : " channel started") + " on " + body.m_unit.GetId());
				return;
			}
			if (sub == "heresy" && args.length() >= 2)
			{
				int want = int(parseInt(args[1]));
				AddHeresy(plr, want - Heresy(plr));
				HWP::Commands::Reply("forge: heresy " + Heresy(plr));
				return;
			}
			if (sub == "roll" && args.length() >= 3)
			{
				// the lunge's die, thrown n times in one frame: how often randf() lands under the chance
				// (plan-forgemaster 20261022-102006 saw 0 lunges in 25 bodies at 16%)
				int n = int(parseInt(args[1]));
				float c = parseFloat(args[2]);
				int hits = 0;
				for (int i = 0; i < n; i++)
					if (randf() < c)
						hits++;
				HWP::Commands::Reply("forge: roll " + hits + " of " + n + " under " + c);
				return;
			}
			if (sub == "lunge")
			{
				auto body = PickBody(plr, vec2(0, 0));
				if (body is null)
				{
					HWP::Commands::Reply("forge: no body within " + RAISE_RANGE);
					return;
				}
				body.m_rolled = true;
				Lunge(plr, body);
				HWP::Commands::Reply("forge: lunged at " + body.m_unit.GetId());
				return;
			}
			if (sub == "decay" && args.length() >= 2)
			{
				// hwp forge decay <ms>: every risen's decay clock runs ahead by that much
				int add = int(parseInt(args[1]));
				int n = 0;
				auto risen = RisenUnits(plr);
				for (uint i = 0; i < risen.length(); i++)
				{
					auto r = cast<HWPSpecsRisen>(risen[i]);
					if (r !is null) { r.m_decayAhead += add; n++; }
					auto s = cast<HWPSpecsRisenState>(risen[i]);
					if (s !is null) { s.m_decayAhead += add; n++; }
				}
				HWP::Commands::Reply("forge: decay +" + add + " ms on " + n + " risen");
				return;
			}
			if (sub == "trace")
			{
				// hwp forge trace [on|off]: the risen skill trace (default: toggle)
				g_trace = args.length() >= 2 ? args[1] == "on" : !g_trace;
				HWP::Commands::Reply("forge: trace " + (g_trace ? "on" : "off"));
				return;
			}
			if (sub == "cull")
			{
				auto risen = RisenUnits(plr);
				for (uint i = 0; i < risen.length(); i++)
					DestroyRisen(risen[i]);
				int n = int(risen.length());
				for (uint i = 0; i < g_bodies.length(); i++)
					if (Alive(g_bodies[i].m_unit) && Network::IsServer())
						g_bodies[i].m_unit.Destroy();
				HWP::Commands::Reply("forge: culled " + n + " risen and the bodies");
				return;
			}
			if (sub == "risen")
			{
				auto risen = RisenUnits(plr);
				string ret = "forge risen " + risen.length() + ":";
				for (uint i = 0; i < risen.length(); i++)
					ret += " | " + RisenLine(risen[i], plr);
				HWP::Commands::Reply(ret);
				return;
			}
			if (sub == "bodies")
			{
				PruneBodies();
				string ret = "forge bodies " + g_bodies.length() + ":";
				for (uint i = 0; i < g_bodies.length(); i++)
				{
					auto b = g_bodies[i];
					auto p = b.m_unit.GetPosition();
					ret += " | " + b.m_unit.GetId() + " " + b.m_source.substr(RISEN_DIR.length()) + " at " + int(p.x) + " " + int(p.y)
						+ " ttl " + b.m_ttl + (b.m_boss ? " boss" : b.m_elite ? " elite" : "") + (b.m_rolled ? " rolled" : "")
						+ " glow " + (b.m_glow.IsValid() && !b.m_glow.IsDestroyed() ? 1 : 0);
				}
				HWP::Commands::Reply(ret);
				return;
			}
			PruneBodies();
			string ret = "forge: heresy " + Heresy(plr) + "; favor " + (DivineFavorDef(plr) !is null ? plr.GetStacks(DivineFavorDef(plr)) : -1)
				+ " penance " + (PenanceReady(plr) ? 1 : 0) + "; bodies " + g_bodies.length() + " spawned " + g_bodiesSpawned + " rolls " + g_bodyRolls
				+ "; risen " + RisenCount(plr) + " cap " + BindI(plr, NR, "nr-count", 0) + "; raises " + g_raises + " last " + g_lastRaise
				+ "; penances " + g_penances + "; lunges " + g_lunges + "; blooms " + g_blooms + "; cap kills " + g_capKills
				+ "; decay deaths " + g_decayDeaths + "; moves swapped " + g_movesSwapped + " actions stripped " + g_actionsStripped
				+ "; channel " + (g_channel is null ? "none" : (g_channel.m_penance ? "penance " : "raise ") + g_channel.m_left + " ms")
				+ " locked " + (g_channel !is null && g_channel.m_locked ? 1 : 0) + " beam " + (g_channel !is null && Alive(g_channel.m_beam) ? 1 : 0)
				+ " pulses " + g_chanPulses + " lockface " + g_chanLockFacing + " beamframes " + g_chanBeamFrames
				+ " bar " + (g_chanDrawn ? 1 : 0) + " dashpin " + (g_dashPinned ? 1 : 0) + " dashrefused " + g_chanDashRefused
				+ " dashcd " + (cast<Skills::Charge>(FindSkill(plr, DASH)) !is null ? cast<Skills::Charge>(FindSkill(plr, DASH)).m_cooldownC : -1)
				+ "; icon " + (cast<HWPSpecsResurrection>(FindSkill(plr, NR)) !is null ? cast<HWPSpecsResurrection>(FindSkill(plr, NR)).IconName() : "none")
				+ "; pyreuses " + g_pyreUses + " pyreremoved " + g_pyreHeresyRemoved + " pyrenocurse " + g_pyreNoCurseUses   // no "heresy N" here: the tests read the last one
				+ "; hud " + (g_hudHeresyHigh ? "high" : "low")
				+ "; eat " + (g_eat is null ? "none" : (g_eat.m_dodging ? "dodging" : "eating")) + " bobs " + (g_eat is null ? g_eatBobs : g_eat.m_bobs)
				+ " bloods " + (g_eat is null ? g_eatBloods : g_eat.m_bloods) + " facing " + g_eatFacing
				+ " lift " + (g_eat is null ? 0 : Rounded(plr.m_unit.GetPosition().y - g_eat.m_spot.y))
				+ "; pen lights " + g_penLights + " shine " + g_penFacing + " beside " + g_penBeside + " under " + g_penUnder
				+ "; angle " + Rounded(plr.m_dirAngle * 180 / PI)
				+ "; cd " + (FindSkill(plr, NR) !is null ? cast<Skills::PlayerSkill>(FindSkill(plr, NR)).m_cooldownC : -1)
				+ "; mana " + int(ManaPts(plr) + 0.5f) + "/" + plr.m_record.MaxMana();
			HWP::Commands::Reply(ret);
		}
	}
}

namespace HWPSpecsForgemaster
{
	[Hook]
	void PlayerInitialize(PlayerBase@ player)
	{
		HWP::Specs::OnPlayerInitialize(player);
	}
}

// an intact body: the enemy's scenes, gray, lying (a boss stands), no collision; the module
// handles its 60 s, glow and lunge rolls (HWP::Specs::g_bodies)
class HWPSpecsBody
{
	UnitPtr m_unit;
	string m_source;
	bool m_elite;
	bool m_boss;
	int m_ttl;
	bool m_rolled;
	UnitPtr m_glow;

	HWPSpecsBody(UnitPtr unit, SValue& params)
	{
		m_unit = unit;
		m_source = GetParamString(unit, params, "source", false, "");
		m_elite = GetParamBool(unit, params, "elite", false, false);
		m_boss = GetParamBool(unit, params, "boss", false, false);
		m_ttl = HWP::Specs::BODY_TTL;
		m_rolled = false;
		string idle = GetParamString(unit, params, "idle", false, "idle");
		m_unit.SetUnitScene(AnimString(idle).GetSceneName(PI / 2), true);
		m_unit.SetShouldCollide(false);
		m_unit.SetMultiplyColor(vec4(0.55f, 0.6f, 0.55f, 1.0f));
		if (!m_boss)
			m_unit.SetRotation(PI / 2);
		HWP::Specs::g_bodies.insertLast(this);
	}
}

// the shared part of the two risen classes (a mixin: it reaches the behavior's members)
mixin class HWPSpecsRisenImpl
{
	float m_hpPct = 1.0f;
	float m_dmgMul = 1.0f;
	float m_cohDmg = 0;
	bool m_risenBoss = false;
	int m_decayC = 0;
	int m_decayAhead = 0;
	uint m_seq = 0;
	int m_traceC = 0;
	array<bool> m_wasCasting;

	PlayerBase@ RisenOwner() { return m_ownerRecord is null ? null : cast<PlayerBase>(m_ownerRecord.actor); }

	void RisenSetup()
	{
		Loot = false;
		NoExperience = true;
		Respawn = false;
		auto plr = RisenOwner();
		m_hpPct = HWP::Specs::RisenBind(plr, "nr-hp-pct", 0.5f);
		m_dmgMul = HWP::Specs::RisenBind(plr, "nr-dmg-base", 1.0f) * HWP::Specs::RisenBind(plr, "nr-dmg-pct", 0.5f);
		m_cohDmg = plr is null ? 0 : HWP::Specs::BindF(plr, HWP::Specs::COH, "coh-dmg", 0);
		m_risenBoss = HWP::Specs::HasActorTag(this, "boss");
		m_decayC = m_risenBoss ? HWP::Specs::DECAY_BOSS : HWP::Specs::DECAY_NORMAL;
		m_seq = ++HWP::Specs::g_risenSeq;
		m_props.m_hpRegenTime = 0;
		m_hp = 1.0f;
	}

	void RisenTrace(int dt)
	{
		if (!HWP::Specs::g_trace || m_skills is null)
			return;
		while (m_wasCasting.length() < m_skills.length())
			m_wasCasting.insertLast(false);
		string tgt = m_target is null ? "none" : ("" + m_target.m_unit.GetId() + " at " + int(sqrt(float(distsq(m_unit, m_target)))));
		for (uint i = 0; i < m_skills.length(); i++)
		{
			bool c = m_skills[i].IsCasting();
			if (c && !m_wasCasting[i])
				HWP::Log("specs", "risen " + m_unit.GetId() + " casts skill " + i + " " + Reflect::GetTypeName(m_skills[i]) + " target " + tgt);
			m_wasCasting[i] = c;
		}
		m_traceC -= dt;
		if (m_traceC > 0)
			return;
		m_traceC = 2000;
		string line = "risen " + m_unit.GetId() + " target " + tgt + " skills:";
		for (uint i = 0; i < m_skills.length(); i++)
		{
			auto cs = cast<CompositeActorSkill>(m_skills[i]);
			line += " " + i + ":" + Reflect::GetTypeName(m_skills[i]);
			if (cs !is null)
				line += "(" + (cs.m_restrictions.IsAvailable() ? "avail" : "no") + " cd " + cs.m_cooldownC + (cs.IsCasting() ? " casting" : "") + ")";
			else
				line += (m_skills[i].IsCasting() ? "(casting)" : "");
		}
		// the foes the target search sees (CompositeActorBehavior::QueuedFetchActors): their distance
		// and what the must-see aim ray from here hits first (the target itself, or something in the way)
		vec2 here = xy(m_unit.GetPosition());
		auto foes = g_scene.FetchActorsWithOtherTeam(Team, here, 300);
		line += " foes:";
		for (uint i = 0; i < foes.length() && i < 4; i++)
		{
			auto a = cast<Actor>(foes[i].GetScriptBehavior());
			if (a is null)
				continue;
			RaycastResult res = g_scene.RaycastClosest(here, xy(a.m_unit.GetPosition()), ~0, RaycastType::Aim);
			UnitPtr hit = res.FetchUnit(g_scene);
			line += " " + a.m_unit.GetId() + "@" + int(sqrt(float(distsq(m_unit, a)))) + (a.IsDead() ? " dead" : "")
				+ (a.IsTargetable() ? "" : " untargetable") + " ray " + int(res.fraction * 100) + "% hit "
				+ (hit.IsValid() ? hit.GetId() + ":" + hit.GetDebugName() : "-");
		}
		HWP::Log("specs", line);
	}

	float RisenDamageMul()
	{
		auto plr = RisenOwner();
		return m_dmgMul * (1.0f + (plr is null ? 0 : HWP::Specs::Heresy(plr)) * m_cohDmg);
	}

	void RisenScale(DamageInfo& di)
	{
		float mul = RisenDamageMul();
		di.PhysicalDamage = uint32(di.PhysicalDamage * mul);
		di.FireDamage = uint32(di.FireDamage * mul);
		di.IceDamage = uint32(di.IceDamage * mul);
		di.LightningDamage = uint32(di.LightningDamage * mul);
		di.PoisonDamage = uint32(di.PoisonDamage * mul);
		di.PureDamage = uint32(di.PureDamage * mul);
	}

	int RisenMaxHp()
	{
		float ret = m_props.m_maxHp + (m_props.m_ngpScale * g_ngp * 25);
		ret *= (1.0f + m_props.m_ngpScale * g_ngp * Tweak::EnemyNGPHealthMul);
		float summonMul = Tweak::PlrSummonHealthMul * (m_ownerRecord !is null ? m_ownerRecord.currStats.SummonHealthMul : 1.0f);
		ret *= summonMul * m_hpPct;
		if (!HWP::Specs::HasActorTag(this, "boss"))
			ret = max(ret, HWP::Specs::RISEN_MIN_HP * summonMul);
		return max(1, int(ret));
	}

	// 1% every 3 s (a boss 9 s), on every peer alike; the host calls the death
	void RisenDecay(int dt)
	{
		dt += m_decayAhead;
		m_decayAhead = 0;
		m_decayC -= dt;
		while (m_decayC <= 0)
		{
			m_decayC += m_risenBoss ? HWP::Specs::DECAY_BOSS : HWP::Specs::DECAY_NORMAL;
			m_hp -= HWP::Specs::DECAY_STEP;
			if (float(m_hp) <= 0)
			{
				m_hp = 0.0f;
				if (Network::IsServer())
				{
					HWP::Specs::g_decayDeaths++;
					HWP::Log("specs", "risen " + m_unit.GetId() + " decayed away");
					OnDeath(DamageInfo(), vec2(1, 0));
				}
				return;
			}
		}
	}

	// Rot Bloom: poison for rb-dmg x weapon damage around the dying risen (the host, as for any
	// damage a summon deals: FilterHuskDamage)
	void RisenBloom()
	{
		auto plr = RisenOwner();
		if (plr is null || !Network::IsServer())
			return;
		float rb = HWP::Specs::BindF(plr, HWP::Specs::NR, "rb-dmg", 0);
		if (rb <= 0)
			return;
		vec2 pos = xy(m_unit.GetPosition());
		auto enemies = HWP::Specs::EnemiesNear(pos, HWP::Specs::BLOOM_RADIUS, g_team_player);
		for (uint i = 0; i < enemies.length(); i++)
		{
			auto e = enemies[i];
			if (e is this)
				continue;
			vec2 d = xy(e.m_unit.GetPosition()) - pos;
			DamageInfo di(this, m_weaponInfo);
			di.PoisonDamage = uint32(rb * HWP::Specs::WeaponDamage(plr));
			e.Damage(di, xy(e.m_unit.GetPosition()), lengthsq(d) > 0.01f ? normalize(d) : vec2(1, 0));
		}
		PlayEffect("effects/generic/impacts/poison_impact_1.effect", pos);
		HWP::Specs::g_blooms++;
		HWP::Log("specs", "rot bloom on " + enemies.length() + " enemies for " + int(rb * HWP::Specs::WeaponDamage(plr)));
	}
}

class HWPSpecsRisen : PlayerOwnedActor, HWPSpecsRisenImpl
{
	HWPSpecsRisen(UnitPtr unit, SValue& params) { super(unit, params); }

	void Initialize(Actor@ owner, float intensity, bool husk, uint weaponInfo = 0) override
	{
		PlayerOwnedActor::Initialize(owner, intensity, husk, weaponInfo);
		RisenSetup();
		auto nm = HWP::Specs::FollowerFor(m_unit, this, m_movement);
		if (nm !is null)
		{
			@m_movement = nm;
			m_movement.ActivateMovement();
		}
		HWP::Specs::StripSkills(m_skills);
	}

	int GetMaxHp() override { return RisenMaxHp(); }
	int Heal(int amount, bool pickup) override { return 0; }
	void NetHeal(int amt) override {}

	// Divine Protection's base-rank aura (aura-buff null, range 1) reaches a summon that has just
	// teleported onto the priest: ApplyBuff with no def threw in CompositeActorBehavior (line 514)
	bool ApplyBuff(ActorBuff@ buff) override
	{
		if (buff is null || buff.m_def is null)
			return false;
		return PlayerOwnedActor::ApplyBuff(buff);
	}

	DamageInfo DamageActor(Actor@ actor, DamageInfo di) override
	{
		RisenScale(di);
		return PlayerOwnedActor::DamageActor(actor, di);
	}

	void TriggerOnDeath(DamageInfo di, vec2 dir, bool local = true) override
	{
		if (!m_dead && !m_unit.IsDestroyed())
			RisenBloom();
		PlayerOwnedActor::TriggerOnDeath(di, dir, local);
	}

	void Update(int dt) override
	{
		PlayerOwnedActor::Update(dt);
		if (!IsDead() && !m_unit.IsDestroyed())
		{
			RisenDecay(dt);
			RisenTrace(dt);
		}
	}
}

class HWPSpecsRisenState : PlayerOwnedStateActor, HWPSpecsRisenImpl
{
	HWPSpecsRisenState(UnitPtr unit, SValue& params) { super(unit, params); }

	void Initialize(Actor@ owner, float intensity, bool husk, uint weaponInfo = 0) override
	{
		PlayerOwnedStateActor::Initialize(owner, intensity, husk, weaponInfo);
		RisenSetup();
		// every state: its own movement swapped once (states share the base movement)
		array<ActorMovement@> olds;
		array<ActorMovement@> news;
		for (uint i = 0; i < m_states.length(); i++)
		{
			auto st = m_states[i];
			st.m_props.m_hpRegenTime = 0;
			if (st.m_movement is null)
				continue;
			int k = olds.findByRef(st.m_movement);
			if (k < 0)
			{
				olds.insertLast(st.m_movement);
				news.insertLast(HWP::Specs::FollowerFor(m_unit, this, st.m_movement));
				k = int(olds.length()) - 1;
			}
			if (news[k] !is null)
				@st.m_movement = news[k];
			HWP::Specs::StripSkills(st.m_skills);
		}
		HWP::Specs::StripSkills(m_baseSkills);
		if (m_currState !is null && m_currState.m_movement !is null)
		{
			@m_movement = m_currState.m_movement;
			m_movement.ActivateMovement();
		}
	}

	int GetMaxHp() override { return RisenMaxHp(); }
	int Heal(int amount, bool pickup) override { return 0; }
	void NetHeal(int amt) override {}

	// Divine Protection's base-rank aura (aura-buff null, range 1) reaches a summon that has just
	// teleported onto the priest: ApplyBuff with no def threw in CompositeActorBehavior (line 514)
	bool ApplyBuff(ActorBuff@ buff) override
	{
		if (buff is null || buff.m_def is null)
			return false;
		return PlayerOwnedStateActor::ApplyBuff(buff);
	}

	DamageInfo DamageActor(Actor@ actor, DamageInfo di) override
	{
		RisenScale(di);
		return PlayerOwnedStateActor::DamageActor(actor, di);
	}

	void TriggerOnDeath(DamageInfo di, vec2 dir, bool local = true) override
	{
		if (!m_dead && !m_unit.IsDestroyed())
			RisenBloom();
		PlayerOwnedStateActor::TriggerOnDeath(di, dir, local);
	}

	void Update(int dt) override
	{
		PlayerOwnedStateActor::Update(dt);
		if (!IsDead() && !m_unit.IsDestroyed())
		{
			RisenDecay(dt);
			RisenTrace(dt);
		}
	}
}

// in Necrotic Resurrection's modifiers: risen producers are not held to one summon each
class HWPSpecsRisenCap : Modifiers::Modifier
{
	HWPSpecsRisenCap(UnitPtr unit, SValue& params) {}

	Modifiers::ModDynamism HasModifyPlayerSummons() override { return Modifiers::ModDynamism::Dynamic; }
	void ModifyPlayerSummons(PlayerBase@ player, float intensity) override
	{
		auto@ summons = player.m_record.summons;
		for (uint i = 0; i < summons.length(); i++)
		{
			if (summons[i].m_prod !is null && summons[i].m_prod.GetResourceName().findFirst(HWP::Specs::RISEN_DIR) == 0)
				summons[i].m_maxSummons = 1000;
		}
	}
}

// Necrotic Resurrection / Sacrificial Penance
class HWPSpecsResurrection : Skills::PlayerSkillDirectional
{
	bool m_penanceCast;
	ScriptSprite@ m_iconRaise;
	ScriptSprite@ m_iconPenance;

	HWPSpecsResurrection(UnitPtr unit, SValue& params) { super(unit, params); }

	void Initialize(Actor@ owner, UnitPtr unit, array<SValue@>@ params, uint id) override
	{
		Skills::PlayerSkillDirectional::Initialize(owner, unit, params, id);
		@m_iconPenance = ScriptSprite(Resources::GetTexture2D("players/hwp/specs/icons.png"), vec4(120, 144, 24, 24));
		// m_icon is still null here: PlayerBase.LoadSkills assigns `@skill.m_icon = def.m_icon` AFTER
		// Initialize (PlayerBase.as LoadSkills), so the raise icon is taken on the first RefreshIcon
		// instead (the icon never swapped before, the user 2026-10-25)
	}

	// the HUD's SkillWidget draws skill.m_icon every frame, so swapping it here is enough
	void RefreshIcon(bool penance)
	{
		if (m_iconRaise is null)
		{
			if (m_icon is null || m_icon is m_iconPenance)
				return;
			@m_iconRaise = m_icon;
		}
		ScriptSprite@ want = penance ? m_iconPenance : m_iconRaise;
		if (m_icon is want)
			return;
		@m_icon = want;
		HWP::Log("specs", "resurrection icon -> " + (penance ? "penance" : "raise"));
	}

	// for `hwp forge`: which icon the skill shows now
	string IconName()
	{
		if (m_icon is null)
			return "null";
		if (m_icon is m_iconPenance)
			return "penance";
		if (m_icon is m_iconRaise)
			return "raise";
		return "unset";
	}

	bool CanActivate(bool warn = true) override
	{
		auto plr = cast<PlayerBase>(m_owner);
		if (plr !is null && HWP::Specs::IsLocal(plr))
		{
			bool blocked = HWP::Specs::g_channel !is null
				|| (!HWP::Specs::PenanceReady(plr) && HWP::Specs::Heresy(plr) >= HWP::Specs::HERESY_BLOCK)
				|| HWP::Specs::PickBody(plr, vec2(0, 0)) is null;
			if (blocked)
			{
				if (warn)
					plr.m_record.PlayVoice("cant");
				return false;
			}
		}
		return Skills::PlayerSkillDirectional::CanActivate(warn);
	}

	PointCost@ GetCost() override
	{
		auto plr = cast<PlayerBase>(m_owner);
		if (m_penanceCast || (m_castingT < 0 && plr !is null && HWP::Specs::PenanceReady(plr)))
			return PointCost(0, HWP::Specs::PENANCE_MANA);
		return Skills::PlayerSkillDirectional::GetCost();
	}

	void NetActivate(vec2 target, float intensity) override
	{
		auto plr = cast<PlayerBase>(m_owner);
		m_penanceCast = plr !is null && HWP::Specs::PenanceReady(plr);
		Skills::PlayerSkillDirectional::NetActivate(target, intensity);
		if (plr !is null && HWP::Specs::IsLocal(plr))
		{
			// the engine spends a skill's cost at its castpoint (PlayerSkillDirectional::Update), which
			// the raising buff's silence never lets this cast reach: the channel spends it, and starts
			// a raise's cooldown, when it completes (CompleteChannel), so a cancelled channel costs
			// nothing (CanActivate has checked the cost can be paid)
			auto body = HWP::Specs::PickBody(plr, target);
			if (body !is null)
				HWP::Specs::StartChannel(plr, body, m_penanceCast, -1, this, GetCost());
		}
	}

	// a raise's cooldown, from the completed channel: the raising buff's silence ends the cast
	// before the castpoint where the engine would start it
	void StartRaiseCooldown()
	{
		m_cooldownC = int(m_cooldown * m_modCooldownMul);
	}

	// a Penance starts no cooldown
	void Deactivate() override
	{
		int cd = m_cooldownC;
		Skills::PlayerSkillDirectional::Deactivate();
		if (m_penanceCast)
			m_cooldownC = cd;
		m_penanceCast = false;
	}
}

// Pyre Sacrifice: the Pyre (class swap of doodads/lamps/brazier_pyre.unit) also removes Heresy,
// and a Forgemaster with Heresy can use it with no curse. The large pyre (WorldScript::Pyre, the
// module's override of scripts/WorldScript/Pyre.as) calls the same two helpers.
namespace HWP
{
	namespace Specs
	{
		int g_pyreUses = 0, g_pyreHeresyRemoved = 0, g_pyreNoCurseUses = 0;

		// the vanilla CanUse wants a curse: a local Forgemaster with Heresy may use the pyre without
		// one (the user, 2026-10-25: "pyres shouldn't require you to have curse if you have heresy"),
		// when Pyre Sacrifice would take some Heresy off; without the orb the use would only spend
		// the pyre
		bool PyreHeresyAllows(PlayerBase@ player)
		{
			return player !is null && IsLocal(player) && Learned(player, NR) && Heresy(player) > 0
				&& BindI(player, NR, "ps-reduce", 0) > 0;
		}

		// after the vanilla Use on the user's own client: Pyre Sacrifice's Heresy, counted and logged
		void PyreHeresyUsed(PlayerBase@ player, const string &in kind, int cursesBefore)
		{
			if (player is null || !IsLocal(player))
				return;
			g_pyreUses++;
			if (cursesBefore <= 0)
				g_pyreNoCurseUses++;
			int rm = min(BindI(player, NR, "ps-reduce", 0), Heresy(player));
			if (rm > 0)
			{
				AddHeresy(player, -rm);
				g_pyreHeresyRemoved += rm;
				AddFloatingText(FloatingTextType::Pickup, "-" + rm + " Heresy", player.m_unit.GetPosition());
			}
			Log("specs", kind + " pyre used" + (cursesBefore <= 0 ? " with no curse" : "") + ": heresy -" + rm + " -> " + Heresy(player));
		}
	}
}

class HWPSpecsPyre : PyreUnitBehavior
{
	HWPSpecsPyre(UnitPtr unit, SValue& params) { super(unit, params); }

	bool CanUse(PlayerBase@ player) override
	{
		if (PyreUnitBehavior::CanUse(player))
			return true;
		// the vanilla refusals: used already (stays), or a local player with no curse
		if (player is null || (m_used && player.m_record.local))
			return false;
		return HWP::Specs::PyreHeresyAllows(player);
	}

	void Use(PlayerBase@ player) override
	{
		bool was = m_used;
		int curses = player !is null ? player.m_record.shadowCurses : 0;
		PyreUnitBehavior::Use(player);
		if (was || player is null)
			return;
		HWP::Specs::PyreHeresyUsed(player, "brazier", curses);
	}
}
