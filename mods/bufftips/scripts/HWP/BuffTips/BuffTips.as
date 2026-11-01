// Buff tooltips: hovering a buff or debuff icon in the HUD's buff bar shows a
// tooltip with the effect's name, its description and, above it, the seconds
// it has left, counting down. HUD components get no mouse input, so
// HWPBuffTipsHUD hit-tests the cursor against the HUDBuffs icons itself every
// frame and draws a vanilla ToolTip (CreateTitledTooltip, header = time left) on top
// of the HUD. Buffs without a "hud" icon never reach the buff bar, so they
// have no tooltip either; their text still shows in the character menu's
// Effects tab. Vanilla's class skill buffs that have no icon (War Cry and
// others, SkillBuffs.as) get one here (ApplySkillIcons). Settings:
// bufftips.enabled, bufftips.skill_icons.
namespace HWP
{
	namespace BuffTips
	{
		// lang key -> text; empty and the placeholder "title" mean no text
		string Text(const string &in s)
		{
			if (s.isEmpty() || s == "title")
				return "";
			return s.substr(0, 1) == "." ? Resources::GetString(s) : s;
		}

		// name and description of whatever kind of buff the icon shows
		string Describe(IBuffWidgetInfo@ info, string &out desc)
		{
			desc = "";
			auto buff = cast<ActorBuff>(info);
			if (buff !is null && buff.m_def !is null)
			{
				desc = Text(buff.m_def.m_description);
				return Text(buff.m_def.m_name);
			}
			auto stacked = cast<ActorBuffStacked>(info);
			if (stacked !is null && stacked.m_def !is null)
			{
				string name = Text(stacked.m_def.m_name);
				if (!name.isEmpty())
				{
					desc = Text(stacked.m_def.m_desc);
					return name;
				}
				if (stacked.m_def.m_buffDef !is null)
				{
					desc = Text(stacked.m_def.m_buffDef.m_description);
					return Text(stacked.m_def.m_buffDef.m_name);
				}
				return "";
			}
			auto skill = cast<Skills::Skill>(info);
			if (skill !is null)
				return Text(skill.m_name);
			return "";
		}

		// Read display fields without constructing a gameplay ActorBuffDef. Loading all
		// buff gameplay data just to install icons also loads unused class modifiers.
		class SkillBuffDisplay
		{
			uint hash;
			int iconX;
			string name;
			string description;
			bool valid = true;
		}

		class SkillIconOwner
		{
			ActorBuffDef@ def;
			ScriptSprite@ sprite;
			uint hash;
		}

		array<SkillBuffDisplay@> g_skillDisplay;
		array<SkillIconOwner@> g_iconOwners;
		array<ActorBuffDef@> g_seenDefs;
		array<uint> g_seenHashes;
		array<ActorBuffDef@> g_changedWidgetDefs;
		HUD@ g_seenHUD;
		HUDBuffs@ g_seenBuffComponent;
		Widget@ g_seenBuffList;
		PlayerRecord@ g_seenHUDRecord;
		Actor@ g_seenHUDActor;
		bool g_displayReady = false;
		string g_iconLog;

		bool DisplayString(SValue@ raw, const string &in key, const string &in fallback, string &out value)
		{
			auto field = HWP::SV::Field(raw, key);
			if (field is null)
			{
				value = fallback;
				return true;
			}
			if (field.GetType() != SValueType::String)
				return false;
			value = field.GetString();
			if (value.isEmpty())
				value = fallback;
			return true;
		}

		void ResolveSkillDisplay()
		{
			if (g_displayReady)
				return;
			g_displayReady = true;
			if (SKILL_BUFF_ICON_X.length() != SKILL_BUFFS.length() || SKILL_BUFF_NAMES.length() != SKILL_BUFFS.length()
				|| SKILL_BUFF_DESCS.length() != SKILL_BUFFS.length())
			{
				HWP::LogError("bufftips", "skill buff metadata: table lengths differ");
				return;
			}
			for (uint i = 0; i < SKILL_BUFFS.length(); i++)
			{
				SkillBuffDisplay display;
				display.hash = HashString(SKILL_BUFFS[i]);
				display.iconX = SKILL_BUFF_ICON_X[i];
				// Only borrowed raw display fields are read. No raw SValue survives this call.
				auto raw = Resources::GetSValue(display.hash);
				display.valid = raw !is null && raw.GetType() == SValueType::Dictionary;
				if (display.valid)
				{
					auto hud = HWP::SV::Field(raw, "hud");
					display.valid = (hud is null || hud.GetType() == SValueType::Array)
						&& DisplayString(raw, "name", SKILL_BUFF_NAMES[i], display.name)
						&& DisplayString(raw, "description", SKILL_BUFF_DESCS[i], display.description);
				}
				// A duplicated table hash cannot choose metadata for an unrelated definition.
				for (uint j = 0; j < g_skillDisplay.length(); j++)
				{
					if (g_skillDisplay[j].hash == display.hash)
					{
						g_skillDisplay[j].valid = false;
						display.valid = false;
					}
				}
				g_skillDisplay.insertLast(display);
				if (!display.valid)
					HWP::LogError("bufftips", "invalid skill buff display metadata: " + SKILL_BUFFS[i]);
			}
			uint valid = 0;
			for (uint i = 0; i < g_skillDisplay.length(); i++)
				if (g_skillDisplay[i].valid)
					valid++;
			HWP::Log("bufftips", "skill buff metadata: " + valid + " of " + SKILL_BUFFS.length()
				+ " raw definitions available, " + (SKILL_BUFFS.length() - valid) + " invalid");
		}

		SkillBuffDisplay@ DisplayFor(uint hash)
		{
			for (uint i = 0; i < g_skillDisplay.length(); i++)
				if (g_skillDisplay[i].valid && g_skillDisplay[i].hash == hash)
					return g_skillDisplay[i];
			return null;
		}

		int IconOwner(ActorBuffDef@ def)
		{
			for (uint i = 0; i < g_iconOwners.length(); i++)
				if (g_iconOwners[i].def is def)
					return int(i);
			return -1;
		}

		array<ActorBuffDef@>@ LoadedSkillDefs()
		{
			array<ActorBuffDef@> defs;
			for (uint i = 0; i < g_actorBuffDefs.length(); i++)
				if (g_actorBuffDefs[i] !is null && defs.findByRef(g_actorBuffDefs[i]) < 0)
					defs.insertLast(g_actorBuffDefs[i]);
			// Include an active native def even if a cache entry was replaced in place.
			for (uint p = 0; p < g_players.length(); p++)
			{
				if (g_players[p] is null)
					continue;
				auto player = cast<PlayerBase>(g_players[p].actor);
				if (player is null || player.m_buffs is null)
					continue;
				auto@ buffs = player.m_buffs.m_buffs;
				for (uint i = 0; i < buffs.length(); i++)
					if (buffs[i] !is null && buffs[i].m_duration > 0 && buffs[i].m_def !is null && defs.findByRef(buffs[i].m_def) < 0)
						defs.insertLast(buffs[i].m_def);
			}
			return defs;
		}

		void WidgetDefChanged(ActorBuffDef@ def)
		{
			if (g_changedWidgetDefs.findByRef(def) < 0)
				g_changedWidgetDefs.insertLast(def);
		}

		HUDBuffs@ SkillBuffComponent(HUD@ hud)
		{
			for (uint i = 0; hud !is null && i < hud.m_components.length(); i++)
			{
				auto component = cast<HUDBuffs>(hud.m_components[i]);
				if (component !is null)
					return component;
			}
			return null;
		}

		void HideOwnedListWidgets()
		{
			if (g_seenBuffList is null)
				return;
			for (uint i = 0; i < g_seenBuffList.m_children.length(); i++)
			{
				auto widget = cast<BuffWidget>(g_seenBuffList.m_children[i]);
				if (widget is null)
					continue;
				auto buff = cast<ActorBuff>(widget.m_buff);
				if (buff is null || buff.m_def is null)
					continue;
				int ours = IconOwner(buff.m_def);
				if (ours < 0 || buff.m_def.m_hud !is g_iconOwners[ours].sprite)
					continue;
				widget.m_visible = false;
				if (buff.m_hudIcon is widget)
					@buff.m_hudIcon = null;
			}
		}

		void ObserveSkillHUD()
		{
			auto hud = GetHUD();
			auto component = SkillBuffComponent(hud);
			Widget@ list;
			if (component !is null)
				@list = component.m_wBuffList;
			PlayerRecord@ record;
			auto gm = cast<AGameplayGameMode>(g_gameMode);
			if (gm !is null && gm.m_spectating)
			{
				if (gm.m_spectatingPlayer >= 0 && uint(gm.m_spectatingPlayer) < g_players.length())
					@record = g_players[gm.m_spectatingPlayer];
			}
			else
				@record = GetLocalPlayerRecord();
			Actor@ actor;
			if (record !is null)
				@actor = record.actor;
			if (hud is g_seenHUD && component is g_seenBuffComponent && list is g_seenBuffList
				&& record is g_seenHUDRecord && actor is g_seenHUDActor)
				return;
			// The old display actor may already have left its record. Its widgets
			// are still discoverable in the old list, without retaining actor state.
			HideOwnedListWidgets();
			@g_seenHUD = hud;
			@g_seenBuffComponent = component;
			@g_seenBuffList = list;
			@g_seenHUDRecord = record;
			@g_seenHUDActor = actor;
			for (uint i = 0; i < g_iconOwners.length(); i++)
				if (g_iconOwners[i].def.m_hud is g_iconOwners[i].sprite)
					WidgetDefChanged(g_iconOwners[i].def);
		}

		void HideChangedSkillWidget(ActorBuff@ buff)
		{
			auto widget = cast<BuffWidget>(buff.m_hudIcon);
			IBuffWidgetInfo@ info = buff;
			if (widget !is null && widget.m_buff is info)
				widget.m_visible = false;
			@buff.m_hudIcon = null;
		}

		// A buff can have been applied before its def was patched this frame. The
		// native UpdateHudIcon only updates an existing widget; it never creates one.
		void RefreshChangedSkillWidgets()
		{
			if (g_changedWidgetDefs.length() == 0)
				return;
			auto hud = GetHUD();
			if (hud is null)
				return; // keep the pending definitions until a HUD exists
			auto component = SkillBuffComponent(hud);
			if (component is null || component.m_wBuffList is null)
				return; // the HUD may still be constructing its buff component
			for (uint p = 0; p < g_players.length(); p++)
			{
				if (g_players[p] is null)
					continue;
				auto player = cast<PlayerBase>(g_players[p].actor);
				if (player is null || player.m_buffs is null)
					continue;
				auto@ buffs = player.m_buffs.m_buffs;
				for (uint i = 0; i < buffs.length(); i++)
				{
					auto buff = buffs[i];
					if (buff is null || buff.m_def is null || buff.m_duration <= 0
						|| g_changedWidgetDefs.findByRef(buff.m_def) < 0)
						continue;
					if (buff.m_def.m_hud is null)
					{
						HideChangedSkillWidget(buff);
					}
					else
					{
						int ours = IconOwner(buff.m_def);
						if (ours < 0 || buff.m_def.m_hud !is g_iconOwners[ours].sprite)
							continue; // a later foreign display provider owns this buff now
						auto widget = hud.ShowBuffIcon(player, buff);
						if (widget is null)
							HideChangedSkillWidget(buff); // no longer the displayed player
						else
						{
							@buff.m_hudIcon = widget;
							widget.m_visible = true;
						}
					}
				}
			}
			g_changedWidgetDefs.resize(0);
		}

		void ApplySkillIcons()
		{
			ResolveSkillDisplay();
			bool on = HWP::Settings::GetBool("bufftips.skill_icons", true);
			Texture2D@ tex = on ? Resources::GetTexture2D(SKILL_ICONS) : null;
			if (on && tex is null)
			{
				HWP::Log("bufftips", "skill buff icons: " + SKILL_ICONS + " missing");
				return;
			}
			if (!on)
			{
				for (uint i = 0; i < g_iconOwners.length(); i++)
				{
					auto owner = g_iconOwners[i];
					if (owner.def.m_hud is owner.sprite)
					{
						@owner.def.m_hud = null;
						WidgetDefChanged(owner.def);
					}
				}
				g_iconOwners.resize(0);
			}
			auto defs = LoadedSkillDefs();
			// A replaced cache entry may have no active native buff left. Release our
			// old display ownership instead of retaining superseded definitions forever.
			for (int i = int(g_iconOwners.length()) - 1; i >= 0; i--)
			{
				auto owner = g_iconOwners[i];
				if (defs.findByRef(owner.def) >= 0 && owner.def.m_pathHash == owner.hash)
					continue;
				if (owner.def.m_hud is owner.sprite)
				{
					@owner.def.m_hud = null;
					WidgetDefChanged(owner.def);
				}
				g_iconOwners.removeAt(i);
			}
			uint given = 0, own = 0;
			for (uint i = 0; i < defs.length(); i++)
			{
				auto def = defs[i];
				auto display = DisplayFor(def.m_pathHash);
				if (!on || display is null)
					continue;
				int ours = IconOwner(def);
				if (ours >= 0 && def.m_hud !is g_iconOwners[ours].sprite)
				{
					g_iconOwners.removeAt(ours); // another display provider owns it now
					ours = -1;
				}
				if (ours < 0 && def.m_hud !is null)
				{
					own++;
					continue;
				}
				if (ours < 0)
				{
					SkillIconOwner owner;
					@owner.def = def;
					owner.hash = def.m_pathHash;
					@owner.sprite = ScriptSprite(tex, vec4(display.iconX, 0, 14, 14));
					@def.m_hud = owner.sprite;
					g_iconOwners.insertLast(owner);
					WidgetDefChanged(def);
				}
				if (def.m_name.isEmpty())
					def.m_name = display.name;
				if (def.m_description.isEmpty())
					def.m_description = display.description;
				given++;
			}
			g_seenDefs = defs;
			g_seenHashes.resize(defs.length());
			for (uint i = 0; i < defs.length(); i++)
				g_seenHashes[i] = defs[i].m_pathHash;
			string line = "skill buff icons " + (on ? "on" : "off") + ": " + given
				+ " loaded definition(s) given an icon, " + own + " with their own; "
				+ SKILL_BUFFS.length() + " entries in display table";
			if (line != g_iconLog)
				HWP::Log("bufftips", line);
			g_iconLog = line;
			RefreshChangedSkillWidgets();
		}

		void WatchLoadedSkillDefs()
		{
			ObserveSkillHUD();
			auto defs = LoadedSkillDefs();
			bool changed = defs.length() != g_seenDefs.length();
			for (uint i = 0; !changed && i < defs.length(); i++)
				changed = defs[i] !is g_seenDefs[i] || defs[i].m_pathHash != g_seenHashes[i];
			if (changed)
				ApplySkillIcons();
			RefreshChangedSkillWidgets();
		}

		void OnSettingChanged(const string &in key)
		{
			if (key == "bufftips.skill_icons")
				ApplySkillIcons();
		}

	}
}

class HWPBuffTipsHUD : HUDComponent
{
	HUD@ m_hud;
	ToolTip@ m_tip;
	IBuffWidgetInfo@ m_tipBuff;
	int m_tipSecs = -1;
	int m_tipCount = -1;
	vec2 m_mouse;

	HWPBuffTipsHUD(HUD@ hud, GUIBuilder@ b)
	{
		super(b, "");
		@m_hud = hud;
		m_drawOnTop = true;
	}

	HUDBuffs@ Buffs()
	{
		for (uint i = 0; i < m_hud.m_components.length(); i++)
		{
			auto buffs = cast<HUDBuffs>(m_hud.m_components[i]);
			if (buffs !is null)
				return buffs;
		}
		return null;
	}

	// the buff icon under the cursor; the buff bar draws its widgets scaled by
	// its own m_scale (ui_hud_scale_buffs), the cursor is in unscaled HUD units
	BuffWidget@ Hovered()
	{
		auto buffs = Buffs();
		if (buffs is null || !buffs.IsVisible() || buffs.m_wBuffList is null)
			return null;
		float scale = buffs.m_scale;
		auto children = buffs.m_wBuffList.m_children;
		for (uint i = 0; i < children.length(); i++)
		{
			auto w = cast<BuffWidget>(children[i]);
			if (w is null || !w.m_visible || w.m_buff is null || w.m_buff.GetBuffIcon() is null)
				continue;
			vec2 o = (w.m_origin + buffs.m_offset) * scale;
			if (m_mouse.x >= o.x && m_mouse.x < o.x + w.m_width * scale && m_mouse.y >= o.y && m_mouse.y < o.y + w.m_height * scale)
				return w;
		}
		return null;
	}

	void ClearTip()
	{
		if (m_tip !is null)
			m_tip.Cleanup();
		@m_tip = null;
		@m_tipBuff = null;
		m_tipSecs = -1;
		m_tipCount = -1;
	}

	void Update(int dt, PlayerRecord@ record) override
	{
		m_mouse = GetGameModeMousePosition() / g_gameMode.m_wndScale;

		auto gm = cast<BaseGameMode>(g_gameMode);
		bool menuOpen = gm !is null && gm.m_windowManager.GetCurrentWindow() !is null;
		auto w = (!menuOpen && HWP::Settings::GetBool("bufftips.enabled", true)) ? Hovered() : null;
		if (w is null)
		{
			ClearTip();
			return;
		}

		auto info = w.m_buff;
		int left = info.GetBuffIconDuration();
		// no countdown for permanent buffs (kept up by script, e.g. Heroic Legacy)
		int secs = (left > 0 && left < 3600000 && info.GetBuffIconMaxDuration() > 0) ? int(ceil(left / 1000.0f)) : 0;
		int count = info.GetBuffIconCount();
		if (info is m_tipBuff && secs == m_tipSecs && count == m_tipCount)
			return;

		string desc;
		string name = HWP::BuffTips::Describe(info, desc);
		if (name.isEmpty())
			name = Resources::GetString(".hwp.bufftips.unnamed");
		if (count > 1)
			name = Resources::GetString(".hwp.bufftips.stacks", { { "name", name }, { "count", count } });
		string header = secs > 0 ? Resources::GetString(".hwp.bufftips.left", { { "secs", secs } }) : "";

		// once per buff hovered, not per countdown second: a test reads the tip from the log
		if (info !is m_tipBuff)
			HWP::Log("bufftips", "tip: " + name);
		ClearTip();
		if (info.IsDebuff())
			name = "\\cff6666" + name;
		// the titled variant pads the title below the header line (CreateTooltip draws the
		// header over the title), as vanilla does for its headed tooltips (BlueprintBank)
		@m_tip = CreateTitledTooltip(Resources::GetSValue("gui/variable/itemtooltip_common.sval"), name, desc, null, null, Item::Quality::None, header);
		@m_tipBuff = info;
		m_tipSecs = secs;
		m_tipCount = count;
	}

	void Draw(SpriteBatch& sb, int idt) override
	{
		if (m_tip is null)
			return;

		// above and to the right of the cursor (the buff bar is at the bottom),
		// leaving room for the header line drawn over the box, kept on screen
		vec2 size = m_tip.GetSize();
		vec2 pos = m_mouse + vec2(8, -size.y - 6);
		pos.x = min(pos.x, float(g_gameMode.m_wndWidth) - size.x - 2);
		pos.y = max(pos.y, 10.0f);

		mat4 tform;
		tform *= g_gameMode.m_wndInvScaleTransform;
		tform *= mat::scale(mat4(), g_gameMode.m_wndScale);
		sb.PushTransformation(tform);
		m_tip.Draw(sb, vec2(int(pos.x), int(pos.y)));
		sb.PopTransformation();
	}
}

namespace HWPBuffTips
{
	[Hook]
	void HUDConstructor(HUD@ hud, GUIBuilder@ b)
	{
		hud.m_components.insertLast(HWPBuffTipsHUD(hud, b));
	}
}

namespace Modules
{
	class HWPBuffTipsModule : Module
	{
		HWPBuffTipsModule()
		{
			super("hwp-bufftips");
			HWP::Log("bufftips", "ready");
			HWP::BuffTips::ApplySkillIcons();
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::BuffTips::OnSettingChanged));
		}

		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("bufftips", "HWPBuffTipsModule.UpdateFrame"))
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
			HWP::BuffTips::WatchLoadedSkillDefs();
		}

	}
}
