// HoH2 implementations of the level-script types HoH1 levels use and HoH2
// lacks, under the names and Editable parameters the converted levels store
// (tools/import_hoh1.py campaign). Written against HoH2's API; where HoH2 has
// no such system (hardcore, character titles, top numbers) they keep the
// level flowing and do nothing else.
namespace HWP
{
	namespace HoH1
	{
		void Run(array<UnitPtr>@ units)
		{
			for (uint i = 0; i < units.length(); i++)
			{
				auto script = WorldScript::GetWorldScript(g_scene, units[i].GetScriptBehavior());
				if (script !is null)
					script.Execute();
			}
		}

		// The boss level's nodes and room, looked up in the loaded scene (so a
		// previous level can never leak in). The bosses call these on node
		// arrival; per-frame users cache the result for their own lifetime.
		array<WorldScript::BossLichNode@>@ LichNodes()
		{
			array<WorldScript::BossLichNode@> nodes;
			auto res = g_scene.FetchAllWorldScripts("BossLichNode");
			for (uint i = 0; i < res.length(); i++)
			{
				auto node = cast<WorldScript::BossLichNode>(res[i].GetUnit().GetScriptBehavior());
				if (node !is null)
					nodes.insertLast(node);
			}
			return nodes;
		}

		WorldScript::BossLichRoom@ LichRoom()
		{
			auto res = g_scene.FetchAllWorldScripts("BossLichRoom");
			return res.length() == 0 ? null : cast<WorldScript::BossLichRoom>(res[0].GetUnit().GetScriptBehavior());
		}

		WorldScript::VampireCenterNode@ CenterNode()
		{
			auto res = g_scene.FetchAllWorldScripts("VampireCenterNode");
			return res.length() == 0 ? null : cast<WorldScript::VampireCenterNode>(res[0].GetUnit().GetScriptBehavior());
		}

		// Where this floor starts: the default LevelStart of the scene (a HoH1
		// generated floor's start is fabricated before its rooms), else the
		// game's spawn position.
		vec2 FloorStart()
		{
			auto starts = g_scene.FetchAllWorldScripts("LevelStart");
			int prio = -100000;
			vec2 ret = g_spawnPos;
			for (uint i = 0; i < starts.length(); i++)
			{
				auto s = cast<WorldScript::LevelStart>(starts[i].GetUnit().GetScriptBehavior());
				if (s !is null && starts[i].IsEnabled() && s.StartID == "" && s.Priority > prio)
				{
					prio = s.Priority;
					ret = xy(s.Position);
				}
			}
			return ret;
		}

		// the speech bubbles HoH1ShowSpeechBubble opened (HoH1 hides them all at once)
		array<SpeechBubbleContainer@> g_bubbles;
		// HoH1 style file -> its HoH2 style, built once
		dictionary g_bubbleStyles;

		void HideBubbles()
		{
			for (uint i = 0; i < g_bubbles.length(); i++)
				g_bubbles[i].Close();
			g_bubbles.removeRange(0, g_bubbles.length());
		}

		// A HoH1 speech bubble style (its "spriteset" is a SpriteRect file HoH2 reads as
		// is; "tail", "color-text" and "font" beside it) as HoH2's SpeechBubbleStyleDef;
		// HoH2's white one if the file has no spriteset
		SpeechBubbleStyleDef@ BubbleStyle(const string &in path)
		{
			SpeechBubbleStyleDef@ style;
			if (g_bubbleStyles.get(path, @style))
				return style;

			UnitPtr u;
			SValue@ sval = Resources::GetSValue(path);
			string sprites = sval is null ? "" : GetParamString(u, sval, "spriteset", false);
			SValue@ rect = sprites.isEmpty() ? null : Resources::GetSValue(sprites);
			if (rect is null)
			{
				HWP::LogError("campaign", "speech bubble style " + path + " has no spriteset");
				@style = SpeechBubbleStyleDef::Get("white");
			}
			else
			{
				@style = SpeechBubbleStyleDef(rect);
				auto tail = GetParamArray(u, sval, "tail", false);
				if (tail !is null)
					@style.m_tailSprite = ScriptSprite(tail);
				style.m_textColor = ParseColorRGBA(GetParamString(u, sval, "color-text", false, "#000000FF"));
				style.m_font = GetParamString(u, sval, "font", false, "gui/fonts/arial11_nooutline.fnt");
			}
			g_bubbleStyles.set(path, @style);
			return style;
		}
	}
}

namespace WorldScript
{
	[WorldScript color="238 232 170" icon="system/icons.png;160;288;32;32"]
	class SetEnvironment
	{
		[Editable]
		string Environment;

		SValue@ ServerExecute()
		{
			auto env = Resources::GetEnvironment(Environment);
			if (env is null)
			{
				HWP::LogError("campaign", "SetEnvironment: no environment " + Environment);
				return null;
			}
			g_scene.SetEnvironment(env);
			return null;
		}

		void ClientExecute(SValue@ val) { ServerExecute(); }
	}

	// HoH2 has no hardcore characters: always the OnFalse branch
	[WorldScript color="222 111 99" icon="system/icons.png;64;192;32;32"]
	class IsHardcore
	{
		[Editable]
		UnitFeed OnTrue;

		[Editable]
		UnitFeed OnFalse;

		SValue@ ServerExecute()
		{
			HWP::HoH1::Run(OnFalse.FetchAll());
			return null;
		}
	}

	// HoH1 boss kill bookkeeping (achievements, town record): a flag per boss
	// for the rest of the run, which the campaign module can read
	[WorldScript color="200 150 100" icon="system/icons.png;416;384;32;32"]
	class SetBossKilled
	{
		[Editable default=1]
		int BossNumber;

		SValue@ ServerExecute()
		{
			g_flags.Set("hwp_hoh1_boss_" + BossNumber, FlagState::Run);
			HWP::Log("campaign", "HoH1 boss " + BossNumber + " killed");
			return null;
		}

		void ClientExecute(SValue@ val) { ServerExecute(); }
	}

	// HoH1 named its boss bars from the bestiary; tools/import_hoh1.py writes those
	// names as hoh1.bosses.<unit name> (hwp_campaign_hoh1.lang)
	string HoH1BossName(UnitPtr unit)
	{
		auto prod = unit.GetUnitProducer();
		if (prod is null)
			return "";
		string name = prod.GetResourceName();
		int slash = name.findLast("/");
		if (slash >= 0)
			name = name.substr(slash + 1);
		int dot = name.findLast(".");
		if (dot > 0)
			name = name.substr(0, dot);
		return ".hoh1.bosses." + name;
	}

	[WorldScript color="#ff0000" icon="system/icons.png;32;192;32;32"]
	class CreateBossBar
	{
		[Editable]
		UnitFeed Actors;

		[Editable]
		string Name;

		[Editable]
		int SpriteVariation;

		[Editable default="#FF0000FF"]
		vec4 TextColor;

		SValue@ ServerExecute()
		{
			auto hud = g_gameMode.GetHUD();
			if (hud is null)
				return null;
			auto units = Actors.FetchAll();
			for (uint i = 0; i < units.length(); i++)
			{
				auto actor = cast<Actor>(units[i].GetScriptBehavior());
				if (actor !is null)
					hud.AddBossBar(actor, Name.isEmpty() ? HoH1BossName(units[i]) : Name, array<float>());
			}
			return null;
		}

		void ClientExecute(SValue@ val) { ServerExecute(); }
	}

	// HoH1 placed a random group from the level's enemy table here (the
	// dungeon generator's EnemyPlacement.PlaceGroup). Only the battlements use
	// these points, and their table is one entry (GenerateDungeon.as): ice
	// trolls at half density, plus one shaman per group at 0.8 weight. The
	// trolls have no elite, miniboss or spawner units, so nothing else applies.
	[WorldScript color="#bf0000" icon="system/icons.png;32;192;32;32"]
	class SpawnEnemyGroup
	{
		vec3 Position;

		[Editable default=28]
		int Radius;

		SValue@ ServerExecute()
		{
			auto troll = Resources::GetUnitProducer("hoh1/actors/ice_troll_melee.unit");
			auto shaman = Resources::GetUnitProducer("hoh1/actors/ice_troll_shaman.unit");
			if (troll is null)
				return null;

			int num = int(PI * 2 * Radius / 40 * 0.5f);
			bool shamanLeft = shaman !is null;
			for (int i = 0; i < num; i++)
			{
				// EnemyList.GetUnit: the unique is drawn with weight 0.8
				// against the single normal unit, then removed
				UnitProducer@ prod = troll;
				if (shamanLeft && randf() * 1.8f >= 1.0f)
				{
					@prod = shaman;
					shamanLeft = false;
				}
				vec2 pos = xy(Position) + randdir() * float(randi(Radius - 5));
				// EnemyList.GetUnit also ran its pick through UnitMap::Replace (NG+ copies)
				SpawnUnitBaseImpl(HWP::HoH1::TierFor(prod), pos, "", 0, 0, UnitPtr(), 0, 1.0f, 0);
			}
			return null;
		}
	}

	[WorldScript color="176 196 222" icon="system/icons.png;96;96;32;32"]
	class RandomLoot
	{
		vec3 Position;

		[Editable default=false]
		bool Forced;

		SValue@ ServerExecute() { return null; }
	}

	[WorldScript color="255 0 0" icon="system/icons.png;32;32;32;32"]
	class Wind
	{
		vec3 Position;
		bool Enabled;

		[Editable default=100 min=1]
		int Radius;

		[Editable default=0]
		int Direction;

		[Editable default=0.5]
		float Strength;

		[Editable default=1000]
		int ChangeTime;

		float m_intensity = -1.0f;

		// pushes the local player (each client pushes its own; remote players
		// are husks) and every non-player actor in range, as in HoH1
		void Update(int dt)
		{
			if (m_intensity < 0.0f)
				m_intensity = Enabled ? 1.0f : 0.0f;
			float change = 1.0f / max(1, ChangeTime);
			m_intensity = clamp(m_intensity + dt * (Enabled ? change : -change), 0.0f, 1.0f);
			if (m_intensity <= 0.0f)
				return;

			float ang = Direction / 180.0f * PI;
			vec2 push = vec2(cos(ang), sin(ang)) * Strength * m_intensity;
			auto res = g_scene.FetchUnitsWithBehavior("Actor", xy(Position), Radius, true);
			for (uint i = 0; i < res.length(); i++)
			{
				auto actor = cast<Actor>(res[i].GetScriptBehavior());
				if (actor is null || cast<PlayerHusk>(actor) !is null)
					continue;
				if (cast<Player>(actor) is null && !Network::IsServer())
					continue;
				auto body = res[i].GetPhysicsBody();
				if (body !is null)
					body.SetLinearVelocity(body.GetLinearVelocity() + push);
			}
		}
	}

	[WorldScript color="200 150 100" icon="system/icons.png;416;384;32;32"]
	class UnlinkSouls
	{
		SValue@ ServerExecute() { return null; }
	}

	[WorldScript color="200 150 100" icon="system/icons.png;416;384;32;32"]
	class GiveCharacterTitle
	{
		[Editable]
		UnitFeed Targets;

		[Editable]
		int TitleIndex;

		SValue@ ServerExecute() { return null; }
	}

	[WorldScript color="200 150 100" icon="system/icons.png;416;384;32;32"]
	class ClearTopNumbers
	{
		SValue@ ServerExecute() { return null; }
	}

	[WorldScript color="200 150 100" icon="system/icons.png;416;384;32;32"]
	class HideTopNumber
	{
		[Editable]
		string ID;

		SValue@ ServerExecute() { return null; }
	}

	// HoH1's next-floor exit takes the player to the LevelStart of the same StartID
	// (the Battlements' left and right exits); HoH2's starts the next floor at the one
	// of the last StartID set. Every HoH1 exit sets its own, "" for the default start.
	[WorldScript color="255 100 100" icon="system/icons.png;192;288;32;32"]
	class HoH1LevelExitNext
	{
		[Editable]
		string StartID;

		bool m_used;

		SValue@ ServerExecute()
		{
			if (m_used)
				return null;

			g_startId = StartID;
			MissionManager::NextLevel();
			m_used = true;
			return null;
		}
	}

	// HoH1's speech bubble (tools/import_hoh1.py CLASS_MAP): HoH1's style file (its
	// spriteset, tail, text color and font), the title over the text, above the first
	// of Objects, for the ForPlayer player only, until Time runs out (-2: by the text's
	// length, as HoH1; 0: until a HideSpeechBubble). HoH2's bubble has one font, so the
	// title is a line of its own rather than bold.
	[WorldScript color="#A9A9A9" icon="system/icons.png;448;128;32;32"]
	class HoH1ShowSpeechBubble
	{
		[Editable default="hoh1/gui/speechbubbles/white.sval"]
		string Style;

		[Editable]
		string Title;

		[Editable]
		string Text;

		[Editable default=-2]
		int Time;

		[Editable]
		UnitFeed Objects;

		[Editable]
		UnitFeed ForPlayer;

		[Editable default=true]
		bool HideOthers;

		[Editable]
		int HeightOffset;

		SpeechBubbleContainer@ m_current;

		SValue@ ServerExecute()
		{
			ClientExecute(null);
			return null;
		}

		void ClientExecute(SValue@ val)
		{
			UnitPtr plr = ForPlayer.FetchFirst();
			if (plr.IsValid() && cast<Player>(plr.GetScriptBehavior()) is null)
				return;
			UnitPtr unit = Objects.FetchFirst();
			auto style = HWP::HoH1::BubbleStyle(Style);
			if (!unit.IsValid() || style is null)
				return;

			if (HideOthers)
				HWP::HoH1::HideBubbles();
			else
				Hide();

			string text = Resources::GetString(Text);
			string title = Title.isEmpty() ? "" : Resources::GetString(Title);
			int time = Time == -2 ? 1000 + int(text.length()) * 50 : max(0, Time);
			auto entry = SpeechBubbleEntry(time, title.isEmpty() ? text : title + "\n" + text);
			@entry.m_style = style;
			@entry.m_conditionals = ConditionalList();
			@entry.m_effects = EffectList();

			@m_current = SpeechBubbleContainer();
			@m_current.m_speechBubble = entry;
			m_current.m_offset = vec2(0, -18 - HeightOffset);
			m_current.m_unit = unit;
			m_current.Initialize();
			HWP::HoH1::g_bubbles.insertLast(m_current);
		}

		void Hide()
		{
			if (m_current !is null)
				m_current.Close();
			@m_current = null;
		}
	}

	[WorldScript color="#FF4500" icon="system/icons.png;416;256;32;32"]
	class HideSpeechBubble
	{
		[Editable]
		UnitFeed Bubble;

		[Editable]
		UnitFeed ForPlayer;

		SValue@ ServerExecute()
		{
			ClientExecute(null);
			return null;
		}

		void ClientExecute(SValue@ val)
		{
			UnitPtr plr = ForPlayer.FetchFirst();
			if (plr.IsValid() && cast<Player>(plr.GetScriptBehavior()) is null)
				return;
			auto units = Bubble.FetchAll();
			for (uint i = 0; i < units.length(); i++)
			{
				auto bubble = cast<HoH1ShowSpeechBubble>(units[i].GetScriptBehavior());
				if (bubble !is null)
					bubble.Hide();
			}
		}
	}

	[WorldScript color="#FF4500" icon="system/icons.png;416;256;32;32"]
	class HideAllSpeechBubbles
	{
		[Editable]
		UnitFeed ForPlayer;

		SValue@ ServerExecute()
		{
			ClientExecute(null);
			return null;
		}

		void ClientExecute(SValue@ val)
		{
			UnitPtr plr = ForPlayer.FetchFirst();
			if (plr.IsValid() && cast<Player>(plr.GetScriptBehavior()) is null)
				return;
			HWP::HoH1::HideBubbles();
		}
	}

	// boss movement data (the Three Councilors and the Vampire Lord teleport between these)
	[WorldScript color="100 255 100" icon="system/icons.png;96;32;32;32"]
	class BossLichNode
	{
		vec3 Position;

		[Editable]
		UnitFeed NextNodes;

		BossLichNode@ PickNextNode()
		{
			auto nodes = NextNodes.FetchAll();
			if (nodes.length() == 0)
				return null;
			return cast<BossLichNode>(nodes[randi(nodes.length())].GetScriptBehavior());
		}

		SValue@ ServerExecute() { return null; }
	}

	[WorldScript color="100 100 255" icon="system/icons.png;96;32;32;32"]
	class VampireCenterNode : BossLichNode
	{
		BossLichNode@ PickNextNode() override
		{
			// any plain node, never the center itself
			auto nodes = HWP::HoH1::LichNodes();
			for (int i = int(nodes.length()) - 1; i >= 0; i--)
			{
				if (cast<VampireCenterNode>(nodes[i]) !is null)
					nodes.removeAt(i);
			}
			if (nodes.length() == 0)
				return null;
			return nodes[randi(nodes.length())];
		}
	}

	[WorldScript color="100 255 100" icon="system/icons.png;96;32;32;32"]
	class BossLichRoom
	{
		vec3 Position;

		[Editable]
		int Width;

		[Editable]
		int Height;

		bool IsInside(vec3 pos)
		{
			vec2 half = vec2(Width, Height) / 2.0f;
			vec2 d = xy(pos) - xy(Position);
			return abs(d.x) < half.x && abs(d.y) < half.y;
		}

		SValue@ ServerExecute() { return null; }
	}

	// HoH1 elevators banked run gold and ore at home for a tax. HoH2 keeps
	// what a run earns anyway, so the elevator is scenery: same fields, no use.
	[WorldScript color="210 105 30" icon="system/icons.png;96;96;32;32"]
	class StoreOre
	{
		bool Enabled;

		[Editable]
		array<CollisionArea@>@ Areas;

		[Editable]
		UnitFeed Unit;

		[Editable]
		string UseScene;

		SValue@ ServerExecute() { return null; }
	}

	// HoH1 town and dungeon shops (the item forge room). HoH2 has none of
	// those menus, so these are inert until we give them HoH2 shop contents.
	[WorldScript color="#B0C4DE" icon="system/icons.png;384;352;32;32"]
	class ShopArea
	{
		bool Enabled;

		[Editable]
		array<CollisionArea@>@ Areas;

		[Editable default=0]
		int Type;

		[Editable]
		string Category;

		[Editable default=1]
		int ShopLevel;

		[Editable]
		UnitFeed UsedUnits;

		[Editable]
		string UsedUnitScene;

		SValue@ ServerExecute() { return null; }
	}

	// HoH1's generated rooms gate their contents on the distance to the floor's
	// start (no enemies spawned on top of the player): the start the level
	// placed, which the floor generator queues before the rooms (Generator.as).
	[WorldScript color="176 196 222" icon="system/icons.png;384;128;32;32"]
	class CheckSpawnDistance
	{
		vec3 Position;

		[Editable type=enum default=3]
		CompareFunc Function;

		[Editable default=100]
		uint Value;

		[Editable validation=IsExecutable]
		UnitFeed OnTrue;

		[Editable validation=IsExecutable]
		UnitFeed OnFalse;

		bool IsExecutable(UnitPtr unit)
		{
			WorldScript@ script = WorldScript::GetWorldScript(unit);
			return script !is null && script.IsExecutable();
		}

		SValue@ ServerExecute()
		{
			uint ds = uint(dist(HWP::HoH1::FloorStart(), xy(Position)));
			bool result = false;
			switch (Function)
			{
				case CompareFunc::Equal: result = ds == Value; break;
				case CompareFunc::Greater: result = ds > Value; break;
				case CompareFunc::Less: result = ds < Value; break;
				case CompareFunc::GreaterOrEqual: result = ds >= Value; break;
				case CompareFunc::LessOrEqual: result = ds <= Value; break;
				case CompareFunc::NotEqual: result = ds != Value; break;
			}
			HWP::HoH1::Run(result ? OnTrue.FetchAll() : OnFalse.FetchAll());
			return null;
		}
	}

	[WorldScript color="30 210 105" icon="system/icons.png;128;288;32;32"]
	class SetTopNumber
	{
		[Editable]
		string ID;

		[Editable]
		int Number;

		SValue@ ServerExecute() { return null; }
	}
}
