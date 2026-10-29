// gamelab-hands: verbs for the runs test plan (architect loadout, HoH1 bosses).
// pressfunc clicks a button by what it does rather than its id (the loadout's
// rows are all clones with id "rect"), wsexec runs a level's world script the
// way its trigger would, actors adds what a boss is doing (casting skills,
// scene, targetable, moving) to what near reports, rayhit finds where a
// RayProjectile flying from a point would stop (wall or hard tiles), trail
// follows units every frame in-engine (a boss's projectiles live for less
// than a console round trip lets a bot see).
namespace GameLab
{
	// the first visible, enabled interactable under w whose func is name; invisible subtrees are skipped
	AInteractableWidget@ RunsFindFunc(Widget@ w, const string &in name)
	{
		if (w is null || !w.m_visible)
			return null;
		auto iw = cast<AInteractableWidget>(w);
		if (iw !is null && iw.m_enabled && iw.m_func == name)
			return iw;
		for (uint i = 0; i < w.m_children.length(); i++)
		{
			auto found = RunsFindFunc(w.m_children[i], name);
			if (found !is null)
				return found;
		}
		return null;
	}

	// pressfunc <func...>: click the first visible, enabled interactable widget of the top window whose func is that
	void VerbPressFunc(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			Fail(id, "usage: pressfunc <func...>");
			return;
		}
		auto gm = cast<BaseGameMode>(g_gameMode);
		AWindowObject@ wnd;
		if (gm !is null && gm.m_windowManager !is null)
			@wnd = gm.m_windowManager.GetCurrentWindow();
		if (wnd is null || wnd.m_widget is null)
		{
			Fail(id, "no open window");
			return;
		}
		string name = args[0];
		for (uint i = 1; i < args.length(); i++)
			name += " " + args[i];
		auto iw = RunsFindFunc(wnd.m_widget, name);
		if (iw is null)
		{
			Fail(id, "no visible enabled widget with func '" + name + "' in " + Reflect::GetTypeName(wnd));
			return;
		}
		Emit(Reply(id, true).Str("window", Reflect::GetTypeName(wnd)).Str("widget", Reflect::GetTypeName(iw)).Str("wid", iw.m_id));
		iw.ClickDown(false, vec2());
		iw.ClickUp(false, vec2());
	}

	// wsexec <type> <comment>: Execute() the first world script of that type with that comment (host only)
	void VerbWsExec(const string &in id, array<string>@ args)
	{
		if (args.length() < 2)
		{
			Fail(id, "usage: wsexec <type> <comment>");
			return;
		}
		if (!Network::IsServer())
		{
			Fail(id, "wsexec is host only");
			return;
		}
		auto found = g_scene.FetchAllWorldScriptsWithComment(args[0], args[1]);
		if (found.length() == 0)
		{
			Fail(id, "no " + args[0] + " '" + args[1] + "'");
			return;
		}
		auto ws = found[0];
		bool enabled = ws.IsEnabled();
		bool now = ws.CanExecuteNow();
		ws.Execute();
		Emit(Reply(id, true).Int("found", found.length()).Bool("enabled", enabled).Bool("now", now));
	}

	// actors [radius] [filter]: CompositeActorBehavior units within radius (default 400) of the player:
	// position, hp, scene, the skills casting right now, targetable, moving (non-static body), frozen,
	// ally (on the player's team: HoH1's dragon floor shelters the player behind player-team iceblocks)
	void VerbActors(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no spawned local player");
			return;
		}
		int radius = args.length() > 0 ? int(parseInt(args[0])) : 400;
		string filter = args.length() > 1 ? args[1] : "";
		vec2 center = xy(plr.m_unit.GetPosition());
		auto units = g_scene.FetchAllUnits(~0, center, radius);
		array<string> items;
		for (uint i = 0; i < units.length() && items.length() < 32; i++)
		{
			UnitPtr u = units[i];
			if (!u.IsValid() || u.IsDestroyed())
				continue;
			auto a = cast<CompositeActorBehavior>(u.GetScriptBehavior());
			if (a is null)
				continue;
			vec3 pos = u.GetPosition();
			if (dist(center, xy(pos)) > radius)
				continue;
			if (filter != "" && Reflect::GetTypeName(a).findFirst(filter) < 0 && u.GetDebugName().findFirst(filter) < 0)
				continue;
			array<string> casting;
			if (a.m_skills !is null)
			{
				for (uint s = 0; s < a.m_skills.length(); s++)
				{
					if (a.m_skills[s].IsCasting())
						casting.insertLast(Reflect::GetTypeName(a.m_skills[s]));
				}
			}
			auto body = u.GetPhysicsBody();
			Json e;
			e.Int("unit", u.GetId()).Str("name", u.GetDebugName()).Str("behavior", Reflect::GetTypeName(a));
			e.Num("x", pos.x).Num("y", pos.y).Num("hp", a.GetHealth()).Bool("dead", a.IsDead());
			e.Str("scene", u.GetCurrentUnitScene().GetName()).Raw("casting", StrArray(casting));
			e.Bool("targetable", a.IsTargetable()).Bool("moving", body !is null && !body.IsStatic()).Bool("frozen", a.m_frozen)
				.Bool("ally", a.Team == g_team_player);
			items.insertLast(e.Close());
		}
		Emit(Reply(id, true).Int("count", items.length()).Raw("actors", RawArray(items)));
	}

	// projs [radius] [filter]: read-only. The projectiles within radius (default 400) of the player:
	// units whose script behavior's class names a projectile (NewProjectile, RayProjectile,
	// BeamProjectile, their HWP subclasses and the others), with the multiply colour the unit draws
	// with (GetMultiplyColor: what mods/colors' Tint sets), its owner and whether that owner is a
	// player's (GetPlayerOwner, the colors module's friend test). At most 32.
	void VerbProjs(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null)
		{
			Fail(id, "no local player");
			return;
		}
		int radius = args.length() > 0 ? int(parseInt(args[0])) : 400;
		string filter = args.length() > 1 ? args[1] : "";
		vec2 center = xy(plr.m_unit.GetPosition());
		auto units = g_scene.FetchAllUnits(~0, center, radius);
		array<string> items;
		int seen = 0;
		for (uint i = 0; i < units.length(); i++)
		{
			UnitPtr u = units[i];
			if (!u.IsValid() || u.IsDestroyed())
				continue;
			auto b = u.GetScriptBehavior();
			string cls = b is null ? "" : Reflect::GetTypeName(b);
			if (cls.findFirst("Projectile") < 0)
				continue;
			if (filter != "" && cls.findFirst(filter) < 0 && u.GetDebugName().findFirst(filter) < 0)
				continue;
			seen++;
			if (items.length() >= 32)
				continue;
			Actor@ owner = null;
			auto np = cast<NewProjectile>(b);
			if (np !is null)
				@owner = np.m_owner;
			auto rp = cast<RayProjectile>(b);   // and BeamProjectile, a RayProjectile
			if (rp !is null)
				@owner = rp.m_owner;
			vec4 c = u.GetMultiplyColor();
			vec3 pos = u.GetPosition();
			Json e;
			e.Int("unit", u.GetId()).Str("name", u.GetDebugName()).Str("behavior", cls)
				.Num("x", pos.x).Num("y", pos.y).Raw("mul", "[" + formatFloat(c.x, "", 0, 3) + "," + formatFloat(c.y, "", 0, 3)
				+ "," + formatFloat(c.z, "", 0, 3) + "," + formatFloat(c.w, "", 0, 3) + "]")
				.Str("owner", owner is null ? "" : owner.m_unit.GetDebugName())
				.Bool("friendly", owner !is null && GetPlayerOwner(owner) !is null);
			items.insertLast(e.Close());
		}
		Emit(Reply(id, true).Int("count", seen).Raw("projs", RawArray(items)));
	}

	// projshow <unit> <dx> <dy> [friendly]: a projectile unit made at the player + (dx, dy) and
	// initialized like a shot along +x (owner the player when friendly is 1, else none: an enemy
	// shot), then held still (speed 0, a minute to live) so a screenshot can read its pixels. Its
	// tint is whatever the class gives it (mods/colors). Replies the unit and its colours.
	void VerbProjShow(const string &in id, array<string>@ args)
	{
		auto plr = GetLocalPlayer();
		if (plr is null || args.length() < 3)
		{
			Fail(id, plr is null ? "no local player" : "usage: projshow <unit> <dx> <dy> [friendly]");
			return;
		}
		auto prod = Resources::GetUnitProducer(args[0]);
		if (prod is null)
		{
			Fail(id, "no unit " + args[0]);
			return;
		}
		vec3 pos = plr.m_unit.GetPosition() + vec3(parseFloat(args[1]), parseFloat(args[2]), 0);
		UnitPtr u = prod.Produce(g_scene, pos);
		auto proj = cast<IProjectile>(u.GetScriptBehavior());
		if (proj is null)
		{
			if (u.IsValid())
				u.Destroy();
			Fail(id, "not a projectile: " + args[0]);
			return;
		}
		bool friendly = args.length() > 3 && args[3] == "1";
		proj.Initialize(friendly ? cast<Actor>(plr) : null, ProjectileTarget(0.0f), 1.0f, false, 0);
		auto np = cast<NewProjectile>(proj);
		if (np !is null)
		{
			np.m_speed = 0;
			np.m_ttl = 60000;
		}
		vec4 c = u.GetMultiplyColor();
		vec4 o = u.GetOverlayColor();
		Emit(Reply(id, true).Int("unit", u.GetId()).Str("behavior", Reflect::GetTypeName(proj)).Bool("held", np !is null)
			.Raw("mul", "[" + formatFloat(c.x, "", 0, 3) + "," + formatFloat(c.y, "", 0, 3) + "," + formatFloat(c.z, "", 0, 3) + "," + formatFloat(c.w, "", 0, 3) + "]")
			.Raw("overlay", "[" + formatFloat(o.x, "", 0, 3) + "," + formatFloat(o.y, "", 0, 3) + "," + formatFloat(o.z, "", 0, 3) + "," + formatFloat(o.w, "", 0, 3) + "]"));
	}

	// unitcolor <unitId|me> <mul|overlay> <r> <g> <b> [a]: set a unit's multiply or overlay colour
	// (the two ways a sprite takes a colour: SetMultiplyColor scales it, SetOverlayColor blends
	// it toward the colour by a, the damage flash)
	void VerbUnitColor(const string &in id, array<string>@ args)
	{
		if (args.length() < 5)
		{
			Fail(id, "usage: unitcolor <unitId> <mul|overlay> <r> <g> <b> [a]");
			return;
		}
		UnitPtr u;
		auto plr = GetLocalPlayer();
		if (args[0] == "me" && plr !is null)
			u = plr.m_unit;
		else
			u = g_scene.GetUnit(parseInt(args[0]));
		if (!u.IsValid())
		{
			Fail(id, "no unit " + args[0]);
			return;
		}
		vec4 c = vec4(parseFloat(args[2]), parseFloat(args[3]), parseFloat(args[4]), args.length() > 5 ? parseFloat(args[5]) : 1.0f);
		if (args[1] == "overlay")
			u.SetOverlayColor(c);
		else
			u.SetMultiplyColor(c);
		Emit(Reply(id, true).Int("unit", u.GetId()).Str("mode", args[1]));
	}

	// rayhit <x0> <y0> <x1> <y1> [hardness]: where a RayProjectile from (x0,y0) toward (x1,y1) stops:
	// "wall", the first Shot raycast hit that is no damage taker (RayProjectile.HitUnit destroys a
	// bounceless one there), and "tile", the first point (4 px steps) on tiles harder than
	// hardness (default 4, HoH1LurkerProjectile's destroy-at-hardness)
	void VerbRayHit(const string &in id, array<string>@ args)
	{
		if (args.length() < 4)
		{
			Fail(id, "usage: rayhit <x0> <y0> <x1> <y1> [hardness]");
			return;
		}
		vec2 from = vec2(parseFloat(args[0]), parseFloat(args[1]));
		vec2 to = vec2(parseFloat(args[2]), parseFloat(args[3]));
		int hardness = args.length() > 4 ? int(parseInt(args[4])) : 4;
		Json@ r = Reply(id, true);
		bool wall = false;
		array<RaycastResult>@ results = g_scene.Raycast(from, to, ~0, RaycastType::Shot);
		for (uint i = 0; i < results.length() && !wall; i++)
		{
			RaycastResult res = results[i];
			UnitPtr u = res.FetchUnit(g_scene);
			if (u.IsValid() && cast<IDamageTaker>(u.GetScriptBehavior()) !is null)
				continue;
			wall = true;
			r.Num("wx", res.point.x).Num("wy", res.point.y).Num("wd", dist(from, res.point));
			r.Str("wname", u.IsValid() ? u.GetDebugName() : "").Bool("wsensor", res.fixture.IsSensor());
		}
		r.Bool("wall", wall);
		float len = dist(from, to);
		bool tile = false;
		if (len > 0)
		{
			vec2 dir = normalize(to - from);
			for (float d = 0; d <= len && !tile; d += 4.0f)
			{
				vec2 p = from + dir * d;
				auto tilesets = g_scene.FetchTilesets(p);
				for (uint i = 0; i < tilesets.length() && !tile; i++)
				{
					SValue@ data = tilesets[i].GetData();
					SValue@ h = data is null ? null : data.GetDictionaryEntry("hardness");
					if (h is null || h.GetType() != SValueType::Integer || h.GetInteger() <= hardness)
						continue;
					tile = true;
					r.Num("tx", p.x).Num("ty", p.y).Num("td", d).Int("th", h.GetInteger());
				}
			}
		}
		r.Bool("tile", tile);
		Emit(r);
	}

	const uint TRAIL_CAP = 128;   // the NG+1 Warden throws ~30 bombs in 24 s (events come in parts)
	const uint TRAIL_POINTS = 200;
	const uint TRAIL_PART = 13000;   // chars per trail event, under Json.as EMIT_MAX

	string RunsPoint(vec2 p, int t)
	{
		return "[" + int(p.x) + "," + int(p.y) + "," + t + "]";
	}

	// every unit a trail sees: first and last sight (exact to the frame) and a point every step ms
	class RunsTrailTask : QueuedTasks::UpdatingTask
	{
		string m_tag;
		string m_filter;
		int m_radius;
		int m_msLeft;
		int m_step;
		int m_t = 0;
		int m_next = 0;
		int m_truncated = 0;
		array<string> m_plr;

		array<int> m_ids;
		array<string> m_names;
		array<int> m_t0;
		array<int> m_t1;
		array<vec2> m_p0;
		array<vec2> m_p1;
		array<string> m_pts;
		array<int> m_n;

		bool UpdateFrame(int ms) override
		{
			m_t += ms;
			m_msLeft -= ms;
			bool sample = m_t >= m_next;
			if (sample)
				m_next = m_t + m_step;
			auto plr = GetLocalPlayer();
			if (plr !is null)
			{
				vec2 c = xy(plr.m_unit.GetPosition());
				if (sample && m_plr.length() < TRAIL_POINTS)
					m_plr.insertLast(RunsPoint(c, m_t));
				auto units = g_scene.FetchAllUnits(~0, c, m_radius);
				for (uint i = 0; i < units.length(); i++)
				{
					UnitPtr u = units[i];
					if (!u.IsValid() || u.IsDestroyed() || u == plr.m_unit)
						continue;
					vec2 p = xy(u.GetPosition());
					if (dist(c, p) > m_radius)
						continue;
					ref@ b = u.GetScriptBehavior();
					if (m_filter != "" && (b is null || Reflect::GetTypeName(b).findFirst(m_filter) < 0)
						&& u.GetDebugName().findFirst(m_filter) < 0)
						continue;
					int k = m_ids.find(u.GetId());
					bool first = k < 0;
					if (first)
					{
						if (m_ids.length() >= TRAIL_CAP)
						{
							m_truncated++;
							continue;
						}
						m_ids.insertLast(u.GetId());
						m_names.insertLast(u.GetDebugName());
						m_t0.insertLast(m_t);
						m_t1.insertLast(m_t);
						m_p0.insertLast(p);
						m_p1.insertLast(p);
						m_pts.insertLast("");
						m_n.insertLast(0);
						k = int(m_ids.length()) - 1;
					}
					m_t1[k] = m_t;
					m_p1[k] = p;
					if ((first || sample) && uint(m_n[k]) < TRAIL_POINTS)
					{
						m_pts[k] += (m_n[k] > 0 ? "," : "") + RunsPoint(p, m_t);
						m_n[k] = m_n[k] + 1;
					}
				}
			}
			if (m_msLeft > 0)
				return false;

			array<string> items;
			for (uint i = 0; i < m_ids.length(); i++)
			{
				Json e;
				e.Int("unit", m_ids[i]).Str("name", m_names[i]).Int("t0", m_t0[i]).Int("t1", m_t1[i])
					.Num("x0", m_p0[i].x).Num("y0", m_p0[i].y).Num("x1", m_p1[i].x).Num("y1", m_p1[i].y)
					.Raw("pts", "[" + m_pts[i] + "]");
				items.insertLast(e.Close());
			}
			// one event per part, each under the print limit (Json.as EMIT_MAX): the player's
			// points in part 0, the units after them in order
			array<array<string>> parts(1);
			uint used = 2000 + m_plr.length() * 24;
			for (uint i = 0; i < items.length(); i++)
			{
				if (used + items[i].length() + 1 > TRAIL_PART && parts[parts.length() - 1].length() > 0)
				{
					parts.insertLast(array<string>());
					used = 400;
				}
				parts[parts.length() - 1].insertLast(items[i]);
				used += items[i].length() + 1;
			}
			for (uint k = 0; k < parts.length(); k++)
			{
				Json j;
				Emit(j.Str("ev", "trail").Str("tag", m_tag).Int("ms", m_t).Int("truncated", m_truncated)
					.Int("part", int(k)).Int("parts", int(parts.length()))
					.Raw("plr", k == 0 ? RawArray(m_plr) : "[]").Raw("units", RawArray(parts[k])));
			}
			return true;
		}
	}

	// trail <tag> <ms> <radius> <filter> [stepMs]: read-only. For ms of gameplay frames, every unit
	// within radius of the player whose behavior type or .unit path contains filter (as near):
	// first and last sight (time, position) and a point [x,y,ms] every stepMs (default 100), the
	// player's own points too. One {"ev":"trail","tag":...} event when the time is up (a
	// QueuedTasks updating task, so only while a gameplay module ticks), split into "parts" events
	// ("part" 0..) when it would pass the print limit. Capped at TRAIL_CAP units, TRAIL_POINTS
	// points each.
	void VerbTrail(const string &in id, array<string>@ args)
	{
		if (args.length() < 4)
		{
			Fail(id, "usage: trail <tag> <ms> <radius> <filter> [stepMs]");
			return;
		}
		if (QueuedTasks::g_instance is null)
		{
			Fail(id, "no QueuedTasks module");
			return;
		}
		RunsTrailTask task;
		task.m_tag = args[0];
		task.m_msLeft = int(parseInt(args[1]));
		task.m_radius = int(parseInt(args[2]));
		task.m_filter = args[3];
		task.m_step = args.length() > 4 ? max(16, int(parseInt(args[4]))) : 100;
		QueuedTasks::Queue(task);
		Emit(Reply(id, true).Str("tag", task.m_tag).Int("ms", task.m_msLeft).Int("step", task.m_step));
	}

	// statadd <statId> [n]: Stats::Add(HashString(statId), n, the local record), the line a world
	// script's `%STAT Add` makes (WorldScript/Well.as:140 wells-used,
	// WorldScript/Player/SecretFound.as secrets-found); n defaults to 1. Replies the run and
	// character values after (0 for a stat no tweak/stats file defines: Add books nothing).
	// Not the use itself: only what counts it.
	void VerbStatAdd(const string &in id, array<string>@ args)
	{
		auto rec = GetLocalPlayerRecord();
		if (rec is null || args.length() < 1 || args[0].isEmpty())
		{
			Fail(id, rec is null ? "no local character" : "usage: statadd <statId> [n]");
			return;
		}
		int n = args.length() >= 2 ? parseInt(args[1]) : 1;
		uint h = HashString(args[0]);
		Stats::Add(h, n, rec);
		Emit(Reply(id, true).Str("stat", args[0]).Int("run", rec.statsRun is null ? -1 : int(rec.statsRun.GetStatCurr(h)))
			.Int("char", rec.statsChar is null ? -1 : int(rec.statsChar.GetStatCurr(h))));
	}

	void Register_runs()
	{
		RegisterVerb("pressfunc", "<func...>", Verb(VerbPressFunc));
		RegisterVerb("wsexec", "<type> <comment>", Verb(VerbWsExec));
		RegisterVerb("actors", "[radius] [filter]", Verb(VerbActors));
		RegisterVerb("projs", "[radius] [filter]", Verb(VerbProjs));
		RegisterVerb("projshow", "<unit> <dx> <dy> [friendly]", Verb(VerbProjShow));
		RegisterVerb("unitcolor", "<unitId|me> <mul|overlay> <r> <g> <b> [a]", Verb(VerbUnitColor));
		RegisterVerb("rayhit", "<x0> <y0> <x1> <y1> [hardness]", Verb(VerbRayHit));
		RegisterVerb("trail", "<tag> <ms> <radius> <filter> [stepMs]", Verb(VerbTrail));
		RegisterVerb("statadd", "<statId> [n]", Verb(VerbStatAdd));
	}
}
