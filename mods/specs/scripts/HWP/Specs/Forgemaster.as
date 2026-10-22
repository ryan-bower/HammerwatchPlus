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
//   10 s), and UpdateForgemaster finishes it: Heresy +1/+2/+3 and the host raises the body
//   (specs.raise request). At max Divine Favor it is Sacrificial Penance: 3 s, 50 mana, Heresy
//   -(nr-penance + 1 elite + 2 boss), Divine Favor spent, no cooldown.
// - The Heresy lunge: once per body, the first time the Forgemaster is within LUNGE_RANGE,
//   chance Heresy x coh-lunge: the priest jumps to the body, eats it (devouring buff 3 s) and
//   Ravenous Lunge hits the enemies around it.
// - HWPSpecsRisenCap lifts the vanilla one-per-unit summon cap for risen producers; the owner's
//   client keeps the total at nr-count, the oldest going first (EnforceCap, as Player.as does).
// - HWPSpecsPyre (class swap of PyreUnitBehavior): Pyre Sacrifice lowers Heresy on use.
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
		}

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
			@g_channel = null;
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
			if (body is null)
			{
				LogError("specs", "raise: body " + HWP::SV::Int(data, "body", 0) + " is gone");
				return;
			}
			auto rec = GetPlayerRecordByPeer(peer);
			if (rec is null || rec.actor is null)
				return;
			auto prod = Resources::GetUnitProducer(body.m_source);
			if (prod is null)
			{
				LogError("specs", "raise: no risen unit " + body.m_source);
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
		}

		// --- the channel (the caster's client) -------------------------------------------------

		void StartChannel(PlayerBase@ plr, HWPSpecsBody@ body, bool penance, int duration = -1)
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
			@g_channel = c;
			if (duration > 0)
				Give(plr, plr, Buff("raising"), 1.0f, duration);
			Log("specs", (penance ? "penance" : "raise") + " channel " + duration + " ms on " + body.m_unit.GetId());
		}

		void CancelChannel(const string &in why)
		{
			if (g_channel is null)
				return;
			Log("specs", "channel cancelled: " + why);
			@g_channel = null;
		}

		void CompleteChannel()
		{
			auto c = g_channel;
			@g_channel = null;
			if (c is null)
				return;
			auto body = BodyOf(c.m_body);
			auto plr = c.m_plr;
			if (body is null || plr is null || plr.IsDead())
				return;
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
				AddHeresy(plr, body.m_boss ? 3 : body.m_elite ? 2 : 1);
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
			c.m_left -= ms;
			if (c.m_left <= 0)
				CompleteChannel();
		}

		// --- the lunge (the Forgemaster's client) ----------------------------------------------

		void Lunge(PlayerBase@ plr, HWPSpecsBody@ body)
		{
			vec2 pos = xy(body.m_unit.GetPosition());
			auto p = plr.m_unit.GetPosition();
			plr.m_unit.SetPosition(pos.x, pos.y, p.z);
			Give(plr, plr, Buff("devouring"), 1.0f, -1);
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
			RequestBodyGone(body.m_unit);
		}

		void UpdateLunge(PlayerBase@ plr)
		{
			if (plr is null || plr.IsDead() || g_channel !is null)
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

		// the level flags a boss's skills are gated on (CondFlag reads g_flags), which its arena's
		// script sets during the fight: a risen boss asserts them itself (RisenFlags). The face's
		// skills want boss_skills, a totem pole's totem_skills, the bandit's its last room's room_4.
		string FightFlags(const string &in res)
		{
			if (res.findFirst("bosses/boss_face/") >= 0)
				return "boss_skills";
			if (res.findFirst("bosses/boss_totempole/") >= 0)
				return "totem_skills";
			if (res.findFirst("bosses/boss_bandit/") >= 0)
				return "room_4";
			return "";
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
			array<IOwnedUnit@> risen;
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
			while (int(risen.length()) > cap)
			{
				uint oldest = 0;
				for (uint i = 1; i < risen.length(); i++)
				{
					if (RisenSeq(risen[i]) < RisenSeq(risen[oldest]))
						oldest = i;
				}
				auto u = risen[oldest];
				if (Network::IsServer())
					u.Destroy();
				else
					(Network::Message("UnitDestroyed") << u.GetUnit()).SendToHost();
				risen.removeAt(oldest);
				g_capKills++;
				Log("specs", "cap " + cap + ": the oldest risen is gone");
			}
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

		void UpdateForgemaster(int ms)
		{
			auto fm = LocalForgemaster();
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
				auto@ summons = plr.m_record.summons;
				for (uint i = 0; i < summons.length(); i++)
				{
					for (uint j = 0; j < summons[i].m_units.length(); j++)
					{
						auto r = cast<HWPSpecsRisen>(summons[i].m_units[j]);
						if (r !is null) { r.m_decayAhead += add; n++; }
						auto s = cast<HWPSpecsRisenState>(summons[i].m_units[j]);
						if (s !is null) { s.m_decayAhead += add; n++; }
					}
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
				int n = 0;
				auto@ summons = plr.m_record.summons;
				for (uint i = 0; i < summons.length(); i++)
				{
					if (summons[i].m_prod is null || summons[i].m_prod.GetResourceName().findFirst(RISEN_DIR) != 0)
						continue;
					for (uint j = 0; j < summons[i].m_units.length(); j++)
					{
						auto u = summons[i].m_units[j];
						if (u is null || !Alive(u.GetUnit()))
							continue;
						if (Network::IsServer())
							u.Destroy();
						else
							(Network::Message("UnitDestroyed") << u.GetUnit()).SendToHost();
						n++;
					}
				}
				for (uint i = 0; i < g_bodies.length(); i++)
					if (Alive(g_bodies[i].m_unit) && Network::IsServer())
						g_bodies[i].m_unit.Destroy();
				HWP::Commands::Reply("forge: culled " + n + " risen and the bodies");
				return;
			}
			if (sub == "risen")
			{
				string ret = "forge risen " + RisenCount(plr) + ":";
				auto@ summons = plr.m_record.summons;
				for (uint i = 0; i < summons.length(); i++)
				{
					if (summons[i].m_prod is null || summons[i].m_prod.GetResourceName().findFirst(RISEN_DIR) != 0)
						continue;
					for (uint j = 0; j < summons[i].m_units.length(); j++)
					{
						auto u = summons[i].m_units[j];
						if (u !is null && Alive(u.GetUnit()))
							ret += " | " + RisenLine(u, plr);
					}
				}
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
				+ "; hud " + (g_hudHeresyHigh ? "high" : "low")
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
	string m_fightFlags;
	int m_flagC = 0;
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
		m_fightFlags = HWP::Specs::FightFlags(m_unit.GetUnitProducer().GetResourceName());
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

	// the arena flags the boss's skills need, set again every second on every peer (a floor
	// change clears the level flags; the risen comes along)
	void RisenFlags(int dt)
	{
		if (m_fightFlags.isEmpty())
			return;
		m_flagC -= dt;
		if (m_flagC > 0)
			return;
		m_flagC = 1000;
		auto flags = m_fightFlags.split(" ");
		for (uint i = 0; i < flags.length(); i++)
		{
			if (!g_flags.IsSet(flags[i]))
				g_flags.Set(flags[i], FlagState::Level);
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
			RisenFlags(dt);
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
			RisenFlags(dt);
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
		@m_iconRaise = m_icon;
		@m_iconPenance = ScriptSprite(Resources::GetTexture2D("players/hwp/specs/icons.png"), vec4(120, 144, 24, 24));
	}

	void RefreshIcon(bool penance)
	{
		if (m_iconRaise is null)
			return;
		@m_icon = penance ? m_iconPenance : m_iconRaise;
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
			// the raising buff's silence never lets this cast reach: spend it here (CanActivate has
			// already checked it can be paid)
			plr.UsePoints(true, true, GetCost());
			auto body = HWP::Specs::PickBody(plr, target);
			if (body !is null)
				HWP::Specs::StartChannel(plr, body, m_penanceCast);
		}
		// the raising buff silences the priest, which ends this cast before its castpoint (the
		// targeting helper's block), so a raise starts its cooldown here, not in Deactivate
		if (!m_penanceCast)
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

// Pyre Sacrifice: the Pyre (class swap of doodads/lamps/brazier_pyre.unit) also removes Heresy
class HWPSpecsPyre : PyreUnitBehavior
{
	HWPSpecsPyre(UnitPtr unit, SValue& params) { super(unit, params); }

	void Use(PlayerBase@ player) override
	{
		bool was = m_used;
		PyreUnitBehavior::Use(player);
		if (was || player is null || !HWP::Specs::IsLocal(player))
			return;
		int rm = HWP::Specs::BindI(player, HWP::Specs::NR, "ps-reduce", 0);
		if (rm > 0)
		{
			HWP::Specs::AddHeresy(player, -min(rm, HWP::Specs::Heresy(player)));
		}
	}
}
