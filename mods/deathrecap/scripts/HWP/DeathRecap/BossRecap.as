// Boss-fight damage recap. Every machine records its own player's hits on
// boss-tagged actors (PlayerDamagedActor fires only on the attacker's machine:
// CompositeActorBehavior.Damage calls DamagedActor on the local attacker and
// sends the others a UnitDamaged message with no hook). Burn, poison and bleed
// skip that hook: they are the boss's affliction pools, filled by the hits of the
// machine that dealt them and ticked as DoT damage with no hook, so each fight
// follows the pools (BossFight.pool) and counts what ticked off them while the
// local player filled them last ("Afflictions"). It also records the damage it took
// while such a fight was on (PlayerDamageTaken).
//
// A fight is the whole encounter, not one boss unit (issue #33: the Serpents of
// Demise are four boss-tagged serpents feeding one health bar, so every serpent
// that went down showed a recap). Every boss-tagged actor the local player hits
// joins the open fight, and the fight lasts while one of them is alive or the
// HUD still has an undefeated boss bar: vanilla's own notion of an encounter
// (HUDBossBar stacks a bar per boss and clears them once all are down). It takes
// its name from that bar ("Serpents of Demise") when one is up. When it ends
// (polled: IsDead / destroyed, set on every machine by UnitKilled) the machine
// reports its share to the host (bossrecap.report); the host gathers the party's
// reports per fight name for a second and broadcasts the fight
// (bossrecap.show). Every machine then shows the panel (a HUD component), prints
// a chat line per player and logs "[HWP:deathrecap] boss recap <boss>: <name> dealt ...".
namespace HWP
{
	namespace DeathRecap
	{
		const string BOSS_REPORT = "bossrecap.report"; // client -> host: one player's share
		const string BOSS_SHOW = "bossrecap.show";     // host -> all: the whole fight
		const string KEY_BOSS_LAST = "deathrecap.boss_last";
		const int BOSS_GATHER_MS = 1000;  // host: wait this long for the clients' reports
		const int BOSS_TOP = 5;           // sources per player on the panel
		const int BOSS_MAX_PLAYERS = 8;
		const int BOSS_LOG_UNITS = 12;    // "joins" / "down" log lines per fight (the Serpent's body
		                                  // segments are boss units that expire every 4 s)

		// one boss-tagged unit the local player hit in the fight, alive (dropped when it goes down)
		class BossMember
		{
			UnitPtr unit;
			string name;   // BossName when it joined
			int pool;      // its affliction pools as far as the fight has counted them
		}

		class BossFight
		{
			array<BossMember@> members;
			int unitsHit;  // members ever, down ones included
			int unitsDown;
			string boss;
			bool barName;  // named after the HUD's boss bar
			int dealt;
			int taken;
			array<Source@> sources;
		}

		BossFight@ g_fight;              // the encounter the local player is in, or null
		HWPBossRecapHUD@ g_bossHud;

		// host: reports per fight (its name), until the gather timer runs out
		class BossGather
		{
			string boss;
			int left;
			array<SValue@> reports;
		}
		array<BossGather@> g_gathers;

		bool BossEnabled() { return HWP::Settings::GetBool("deathrecap.boss", true); }

		bool IsBoss(Actor@ actor)
		{
			if (actor is null)
				return false;
			return (actor.Tags & ApplyTag(0, g_actorTags.GetTag("boss"))) != 0;
		}

		string BossName(Actor@ actor)
		{
			if (actor is null || !actor.m_unit.IsValid())
				return Resources::GetString(".hwp.deathrecap.unknown");
			auto prod = actor.m_unit.GetUnitProducer();
			if (prod is null)
				return Resources::GetString(".hwp.deathrecap.unknown");
			return Prettify(prod.GetResourceName());
		}

		// the hit's source: the skill that dealt it (its shown name), else "Other"
		string HitSource(PlayerBase@ player, DamageInfo@ dmg)
		{
			if (player !is null && dmg.Weapon != 0)
			{
				auto skill = player.GetSkill(dmg.Weapon);
				if (skill !is null && !skill.m_name.isEmpty())
				{
					if (skill.m_name.substr(0, 1) == ".")
						return Resources::GetString(skill.m_name);
					return skill.m_name;
				}
			}
			return Resources::GetString(".hwp.deathrecap.boss_other");
		}

		BossMember@ MemberOf(BossFight@ fight, Actor@ actor)
		{
			for (uint i = 0; i < fight.members.length(); i++)
			{
				if (fight.members[i].unit == actor.m_unit)
					return fight.members[i];
			}
			return null;
		}

		// the HUD's boss bars: one per actor with a "bossbar" (CompositeActorBehavior adds it
		// when the unit is made), stacked until all are defeated, then cleared
		HUDBossBar@ BossBars()
		{
			HUD@ hud = null;
			if (g_gameMode !is null)
				@hud = g_gameMode.GetHUD();
			for (uint i = 0; hud !is null && i < hud.m_components.length(); i++)
			{
				auto bars = cast<HUDBossBar>(hud.m_components[i]);
				if (bars !is null)
					return bars;
			}
			return null;
		}

		// undefeated boss bars up right now, and the name the HUD shows over them
		int BarsUp(string &out barName)
		{
			barName = "";
			auto bars = BossBars();
			if (bars is null || bars.m_barList is null || bars.m_mainFrame is null || !bars.m_mainFrame.m_visible)
				return 0;
			int up = 0;
			for (uint i = 0; i < bars.m_barList.m_children.length(); i++)
			{
				auto bar = cast<BossBarWidget>(bars.m_barList.m_children[i]);
				if (bar is null || bar.m_actor is null || bar.IsDefeated())
					continue;
				up++;
			}
			if (up > 0 && bars.m_bossName !is null)
				barName = bars.m_bossName.m_str;
			return up;
		}

		bool MemberDown(BossMember@ m)
		{
			if (!m.unit.IsValid() || m.unit.IsDestroyed())
				return true;
			auto actor = cast<Actor>(m.unit.GetScriptBehavior());
			return actor is null || actor.IsDead();
		}

		void AddSource(BossFight@ fight, const string &in src, int amount)
		{
			fight.dealt += amount;
			for (uint i = 0; i < fight.sources.length(); i++)
			{
				if (fight.sources[i].name == src)
				{
					fight.sources[i].amount += amount;
					return;
				}
			}
			Source s;
			s.name = src;
			s.amount = amount;
			fight.sources.insertLast(s);
		}

		int PoolSum(ActorBuffList@ b)
		{
			return b.m_physicalDmgPool + b.m_fireDmgPool + b.m_iceDmgPool + b.m_lightningDmgPool + b.m_poisonDmgPool;
		}

		// what ActorBuffList.AddAffliction adds to the pools for this hit: Damage calls it
		// right after PlayerDamagedActor, with the same mitigated per-type damage
		int AfflictionAdded(CompositeActorBehavior@ boss, DamageInfo@ dmg)
		{
			auto p = boss.m_props;
			if (p is null)
				return 0;
			int physical = int(p.m_afflPhysMul * dmg.PhysicalDamage);
			int fire = int(p.m_afflFireMul * dmg.FireDamage);
			int ice = int(p.m_afflIceMul * dmg.IceDamage);
			int lightning = int(p.m_afflLightnMul * dmg.LightningDamage);
			int poison = int(p.m_afflPoisonMul * dmg.PoisonDamage);
			if (physical <= 0 && fire <= 0 && ice <= 0 && lightning <= 0 && poison <= 0)
				return 0;
			float pm = 0, fm = 0, im = 0, lm = 0, om = 0;
			boss.m_buffs.AfflictionPoolSizeMul(pm, fm, im, lm, om);
			return int(physical * pm) + int(int(fire * fm) * Tweak::FireDmgScale) + int(ice * im)
				+ int(lightning * lm) + int(int(poison * om) * Tweak::PoisonDmgScale);
		}

		// the pools' ticks since the last look: counted when the local player filled them
		// last (m_affectionAttacker; another machine's hits fill that machine's copy of
		// the boss, not this one)
		void CountPoolTicks(BossFight@ fight, BossMember@ m, CompositeActorBehavior@ boss, PlayerRecord@ rec)
		{
			int now = PoolSum(boss.m_buffs);
			int ticked = m.pool - now;
			m.pool = now;
			if (ticked <= 0 || rec is null || rec.actor is null || boss.m_buffs.m_affectionAttacker !is rec.actor)
				return;
			int amount = damage_round(ticked * boss.m_buffs.AfflictionDamageTakenMul());
			if (amount > 0)
				AddSource(fight, Resources::GetString(".hwp.deathrecap.boss_dot"), amount);
		}

		// PlayerDamagedActor: the local player hit something
		void RecordHit(Player@ player, Actor@ actor, DamageInfo@ dmg)
		{
			if (player is null || actor is null || dmg is null || player.m_record is null || !player.m_record.local)
				return;
			if (dmg.Damage <= 0 || !IsBoss(actor) || actor.IsDead())
				return;

			if (g_fight is null)
			{
				BossFight f;
				string barName;
				BarsUp(barName);
				f.barName = !barName.isEmpty();
				f.boss = f.barName ? barName : BossName(actor);
				f.dealt = 0;
				f.taken = 0;
				f.unitsHit = 0;
				f.unitsDown = 0;
				@g_fight = f;
				HWP::Log("deathrecap", "boss fight started: " + f.boss + " (" + BossName(actor) + ", unit " + actor.m_unit.GetId() + ")");
			}
			auto m = MemberOf(g_fight, actor);
			if (m is null)
			{
				BossMember nm;
				nm.unit = actor.m_unit;
				nm.name = BossName(actor);
				auto b = cast<CompositeActorBehavior>(actor);
				nm.pool = b is null ? 0 : PoolSum(b.m_buffs);
				@m = nm;
				g_fight.members.insertLast(nm);
				g_fight.unitsHit++;
				if (g_fight.unitsHit > 1 && g_fight.unitsHit <= BOSS_LOG_UNITS)
					HWP::Log("deathrecap", "boss fight " + g_fight.boss + ": " + nm.name + " (unit " + actor.m_unit.GetId() + ") joins, "
						+ g_fight.unitsHit + " units hit");
			}

			AddSource(g_fight, HitSource(player, dmg), dmg.Damage);
			auto boss = cast<CompositeActorBehavior>(actor);
			if (boss !is null)
			{
				CountPoolTicks(g_fight, m, boss, player.m_record);
				m.pool += AfflictionAdded(boss, dmg);
			}
		}

		// PlayerDamageTaken: the local player was hit while a boss fight is on
		void RecordTaken(Player@ player, DamageInfo@ dmg)
		{
			if (player is null || dmg is null || player.m_record is null || !player.m_record.local)
				return;
			int amount = dmg.DamageDealt > 0 ? dmg.DamageDealt : dmg.Damage;
			if (amount <= 0 || g_fight is null)
				return;
			g_fight.taken += amount;
		}

		void SortSources(array<Source@>& list)
		{
			for (uint i = 0; i + 1 < list.length(); i++)
			{
				uint best = i;
				for (uint j = i + 1; j < list.length(); j++)
					if (list[j].amount > list[best].amount)
						best = j;
				if (best != i)
				{
					auto tmp = list[i];
					@list[i] = list[best];
					@list[best] = tmp;
				}
			}
		}

		SValue@ PackReport(BossFight@ f, PlayerRecord@ rec)
		{
			SortSources(f.sources);
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("units", f.unitsHit);
			b.PushString("boss", f.boss);
			b.PushInteger("peer", rec.peer);
			b.PushString("name", rec.GetName());
			b.PushInteger("dealt", f.dealt);
			b.PushInteger("taken", f.taken);
			b.PushArray("sources");
			for (uint i = 0; i < f.sources.length() && i < uint(BOSS_TOP); i++)
			{
				b.PushDictionary();
				b.PushString("name", f.sources[i].name);
				b.PushInteger("amount", f.sources[i].amount);
				b.PopDictionary();
			}
			b.PopArray();
			b.PopDictionary();
			return b.Build();
		}

		// every machine, each frame: the fight ends once every unit hit in it is down and no
		// undefeated boss bar is left (one serpent of several, a Bandit Lord's mirror image,
		// a spawned ghost going down is not the end)
		void PollFights()
		{
			auto f = g_fight;
			if (f is null)
				return;
			auto rec = GetLocalPlayerRecord();
			for (int i = int(f.members.length()) - 1; i >= 0; i--)
			{
				auto m = f.members[i];
				if (m.unit.IsValid() && !m.unit.IsDestroyed())
				{
					auto boss = cast<CompositeActorBehavior>(m.unit.GetScriptBehavior());
					if (boss !is null)
						CountPoolTicks(f, m, boss, rec);
				}
				if (!MemberDown(m))
					continue;
				f.members.removeAt(i);
				f.unitsDown++;
				if (f.unitsDown <= BOSS_LOG_UNITS)
				{
					string ignored;
					HWP::Log("deathrecap", "boss fight " + f.boss + ": " + m.name + " (unit " + m.unit.GetId() + ") down, "
						+ f.members.length() + " hit units alive, " + BarsUp(ignored) + " boss bars up");
				}
			}
			string barName;
			int bars = BarsUp(barName);
			if (!f.barName && !barName.isEmpty())
			{
				HWP::Log("deathrecap", "boss fight " + f.boss + " is " + barName + " (the boss bar)");
				f.boss = barName;
				f.barName = true;
			}
			if (f.members.length() > 0 || bars > 0)
				return;
			@g_fight = null;
			if (rec is null)
				return;
			HWP::Log("deathrecap", "boss fight over: " + f.boss + ", " + f.unitsHit + " units, " + rec.GetName() + " dealt " + f.dealt + " took " + f.taken);
			HWP::Net::Request(BOSS_REPORT, PackReport(f, rec));
		}

		// host: one player's share of a fight
		void OnBossReport(uint8 peer, SValue@ data)
		{
			if (data is null)
				return;
			// one gather per fight name: the bar's name is the same on every machine (the
			// units each player hit are not)
			string boss = HWP::SV::Str(data, "boss");
			BossGather@ g;
			for (uint i = 0; i < g_gathers.length(); i++)
			{
				if (g_gathers[i].boss == boss)
					@g = g_gathers[i];
			}
			if (g is null)
			{
				BossGather ng;
				ng.boss = boss;
				ng.left = BOSS_GATHER_MS;
				@g = ng;
				g_gathers.insertLast(ng);
			}
			// one report per player (peer: two players may share a display name)
			int from = HWP::SV::Int(data, "peer", int(peer));
			for (int i = int(g.reports.length()) - 1; i >= 0; i--)
			{
				if (HWP::SV::Int(g.reports[i], "peer", -1) == from)
				{
					g.reports[i].Delete();
					g.reports.removeAt(i);
				}
			}
			if (g.reports.length() < uint(BOSS_MAX_PLAYERS))
				g.reports.insertLast(data.Copy()); // the request's data is freed after this handler
		}

		// host, each frame: a gather whose time is up goes out to everyone
		void PollGathers(int ms)
		{
			for (int i = int(g_gathers.length()) - 1; i >= 0; i--)
			{
				auto g = g_gathers[i];
				g.left -= ms;
				if (g.left > 0)
					continue;
				g_gathers.removeAt(i);

				// most damage first
				for (uint a = 0; a + 1 < g.reports.length(); a++)
				{
					uint best = a;
					for (uint b = a + 1; b < g.reports.length(); b++)
						if (HWP::SV::Int(g.reports[b], "dealt") > HWP::SV::Int(g.reports[best], "dealt"))
							best = b;
					if (best != a)
					{
						auto tmp = g.reports[a];
						@g.reports[a] = g.reports[best];
						@g.reports[best] = tmp;
					}
				}

				SValueBuilder b;
				b.PushDictionary();
				b.PushString("boss", g.boss);
				b.PushInteger("count", int(g.reports.length()));
				for (uint r = 0; r < g.reports.length(); r++)
				{
					b.PushSimple("" + r, g.reports[r]); // the builder takes the value
				}
				b.PopDictionary();
				HWP::Log("deathrecap", "boss fight " + g.boss + " ended, broadcasting " + g.reports.length() + " reports");
				g.reports.removeRange(0, g.reports.length());
				HWP::Net::Broadcast(BOSS_SHOW, b.Build());
			}
		}

		// everyone: the fight's summary. Panel, chat lines, log lines, saved text.
		void OnBossShow(SValue@ data)
		{
			if (data is null)
				return;
			string boss = HWP::SV::Str(data, "boss");
			int count = HWP::SV::Int(data, "count");
			int total = 0;
			array<SValue@> reports;
			for (int i = 0; i < count; i++)
			{
				auto r = HWP::SV::Field(data, "" + i);
				if (r is null)
					continue;
				reports.insertLast(r);
				total += HWP::SV::Int(r, "dealt");
			}

			array<string> lines;   // the panel's rows
			array<vec4> colors;
			array<string> saved;
			bool chat = Enabled() && BossEnabled() && HWP::Settings::GetBool("deathrecap.chat", true);
			for (uint i = 0; i < reports.length(); i++)
			{
				auto r = reports[i];
				string name = HWP::SV::Str(r, "name");
				int peer = HWP::SV::Int(r, "peer", 0);
				int dealt = HWP::SV::Int(r, "dealt");
				int taken = HWP::SV::Int(r, "taken");
				vec4 color = ParseColorRGBA("#" + GetPlayerColor(peer) + "ff");

				string header = Resources::GetString(".hwp.deathrecap.boss_player", {
					{ "name", name }, { "dealt", formatThousands(dealt) }, { "pct", "" + Percent(dealt, total) },
					{ "taken", formatThousands(taken) } });
				lines.insertLast(header);
				colors.insertLast(color);

				string srcText;
				string logSrc;
				auto srcV = HWP::SV::Field(r, "sources");
				if (srcV !is null)
				{
					auto srcs = srcV.GetArray();
					for (uint s = 0; srcs !is null && s < srcs.length() && s < uint(BOSS_TOP); s++)
					{
						string sname = HWP::SV::Str(srcs[s], "name");
						int amount = HWP::SV::Int(srcs[s], "amount");
						lines.insertLast("   " + sname + "  " + formatThousands(amount) + "  (" + Percent(amount, dealt) + "%)");
						colors.insertLast(vec4(1, 1, 1, 1));
						if (s < 3)
							srcText += (s > 0 ? ", " : "") + sname + " " + Percent(amount, dealt) + "%";
						logSrc += (s > 0 ? ", " : "") + sname + " " + amount;
					}
				}

				string logLine = "boss recap " + boss + ": " + name + " dealt " + dealt + " (" + Percent(dealt, total) + "%) took " + taken + ": " + logSrc;
				HWP::Log("deathrecap", logLine);
				saved.insertLast(logLine);

				if (chat)
				{
					SValueBuilder cb;
					cb.PushString("\\c" + GetPlayerColor(peer) + name + "\\d "
						+ Resources::GetString(".hwp.deathrecap.boss_chat", {
							{ "dealt", formatThousands(dealt) }, { "boss", boss }, { "pct", "" + Percent(dealt, total) },
							{ "sources", srcText.isEmpty() ? Resources::GetString(".hwp.deathrecap.boss_other") : srcText },
							{ "taken", formatThousands(taken) } }));
					SendSystemMessage("AddChat", cb.Build());
				}
			}

			string joined;
			for (uint i = 0; i < saved.length(); i++)
				joined += (i > 0 ? "\n" : "") + saved[i];
			if (HWP::SaveData::Local() !is null)
				HWP::SaveData::Local().SetString(KEY_BOSS_LAST, joined);

			if (Enabled() && BossEnabled() && g_bossHud !is null)
				g_bossHud.Show(Resources::GetString(".hwp.deathrecap.boss_title", { { "boss", boss }, { "total", formatThousands(total) } }), lines, colors);
		}

		void CmdBossRecap(array<string>@ args)
		{
			int visibleLines = 0;
			bool shown = g_bossHud !is null && g_bossHud.m_visible;
			if (shown)
				visibleLines = int(g_bossHud.m_rows.length());
			HWP::Log("deathrecap", "boss panel " + (shown ? "shown: " + visibleLines + " lines" : "hidden") + ", open fights " + (g_fight is null ? 0 : 1)
				+ (g_fight is null ? "" : " (" + g_fight.boss + ", " + g_fight.unitsHit + " units hit, " + g_fight.members.length() + " alive)"));
			auto last = HWP::SaveData::Local().GetString(KEY_BOSS_LAST, "");
			if (last.isEmpty())
			{
				HWP::Commands::Reply(Resources::GetString(".hwp.deathrecap.boss_none"));
				return;
			}
			auto parts = last.split("\n");
			for (uint i = 0; i < parts.length(); i++)
				HWP::Commands::Reply(parts[i]);
		}
	}
}

// The panel: top middle under the death recap's spot, a title row and one text
// row per line. Goes away after deathrecap.boss_seconds (15) or a click on the
// title row (HUD components get no mouse input, so the row is hit-tested by hand).
class HWPBossRecapHUD : HUDComponent
{
	Widget@ m_panel;
	TextWidget@ m_title;
	TextWidget@ m_close;
	TextWidget@ m_template;
	Widget@ m_rowGroup;
	array<TextWidget@> m_rows;
	int m_left = 0;
	bool m_hover = false;

	HWPBossRecapHUD(GUIBuilder@ b)
	{
		super(b, "gui/hwp_bossrecap.gui");
		@m_panel = m_widget.GetWidgetById("panel");
		@m_title = cast<TextWidget>(m_widget.GetWidgetById("title"));
		@m_close = cast<TextWidget>(m_widget.GetWidgetById("close"));
		@m_template = cast<TextWidget>(m_widget.GetWidgetById("row-template"));
		@m_rowGroup = m_widget.GetWidgetById("rows");
		m_visible = false;
		m_drawOnTop = true;
	}

	void Show(const string &in title, array<string>@ lines, array<vec4>@ colors)
	{
		m_rowGroup.ClearChildren();
		m_rows.removeRange(0, m_rows.length());
		m_title.SetText(title);
		for (uint i = 0; i < lines.length(); i++)
		{
			auto row = cast<TextWidget>(m_template.Clone());
			row.SetID("row-" + i);
			row.m_visible = true;
			row.m_offset = vec2(0, 12 * int(i));
			row.SetText(lines[i]);
			if (i < colors.length())
				row.SetColor(colors[i]);
			m_rowGroup.AddChild(row);
			m_rows.insertLast(row);
		}
		int height = 40 + 12 * int(lines.length());
		m_panel.m_height = height;
		m_widget.GetWidgetById("root").m_height = height;
		m_left = max(1, HWP::Settings::GetInt("deathrecap.boss_seconds", 15)) * 1000;
		m_visible = true;
		Invalidate();
	}

	void Hide()
	{
		m_visible = false;
		m_left = 0;
	}

	bool OverTitle()
	{
		vec2 mouse = GetGameModeMousePosition() / g_gameMode.m_wndScale;
		vec2 o = m_panel.m_origin;
		return mouse.x >= o.x && mouse.x < o.x + m_panel.m_width && mouse.y >= o.y && mouse.y < o.y + 20;
	}

	void Update(int dt, PlayerRecord@ record) override
	{
		if (m_visible)
		{
			m_left -= dt;
			if (m_left <= 0)
				Hide();
			bool hover = OverTitle();
			if (hover != m_hover)
			{
				m_hover = hover;
				m_close.SetColor(ParseColorRGBA(hover ? "#ffffffff" : "#c0c0c0ff"));
			}
			if (hover && GetMenuInput().Forward.Pressed)
				Hide();
		}
		HUDComponent::Update(dt, record);
	}
}

namespace HWPBossRecap
{
	[Hook]
	void PlayerDamagedActor(Player@ player, Actor@ actor, DamageInfo@ di)
	{
		HWP::DeathRecap::RecordHit(player, actor, di);
	}

	[Hook]
	void PlayerDamageTaken(Player@ player, DamageInfo@ dmg)
	{
		HWP::DeathRecap::RecordTaken(player, dmg);
	}

	[Hook]
	void HUDConstructor(HUD@ hud, GUIBuilder@ b)
	{
		auto comp = HWPBossRecapHUD(b);
		hud.m_components.insertLast(comp);
		@HWP::DeathRecap::g_bossHud = comp;
	}
}

namespace Modules
{
	class HWPBossRecapModule : Module, HWP::ModuleStart
	{
		HWPBossRecapModule()
		{
			super("hwp-bossrecap");
			HWP::Net::OnRequest(HWP::DeathRecap::BOSS_REPORT, HWP::Net::RequestHandler(HWP::DeathRecap::OnBossReport));
			HWP::Net::OnEvent(HWP::DeathRecap::BOSS_SHOW, HWP::Net::EventHandler(HWP::DeathRecap::OnBossShow));
			HWP::Commands::Register("bossrecap", " show the last boss fight's damage recap", HWP::Commands::Handler(HWP::DeathRecap::CmdBossRecap));
		}

		void Start(StartMode sMode)
		{
			@HWP::DeathRecap::g_fight = null;
			for (uint i = 0; i < HWP::DeathRecap::g_gathers.length(); i++)
			{
				auto g = HWP::DeathRecap::g_gathers[i];
				for (uint r = 0; r < g.reports.length(); r++)
					g.reports[r].Delete();
			}
			HWP::DeathRecap::g_gathers.removeRange(0, HWP::DeathRecap::g_gathers.length());
			if (HWP::DeathRecap::g_bossHud !is null)
				HWP::DeathRecap::g_bossHud.Hide();
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("deathrecap", "HWPBossRecapModule.UpdateFrame"))
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
			HWP::DeathRecap::PollFights();
			if (Network::IsServer())
				HWP::DeathRecap::PollGathers(ms);
		}
	}
}
