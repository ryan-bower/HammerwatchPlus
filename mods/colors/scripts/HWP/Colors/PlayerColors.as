// Per-player colours on the maps (bugs 10.22.26 line 24). Vanilla already
// colours the name over a player's head and the screen-edge waypoint by peer
// (Tweak::PlayerColors through GetPlayerColor), but every player is the same
// white dot on the minimap, the overlay map (Tab) and the Map tab, and far
// players are nameless there.
//
// Each player's own minimap sprite is tinted their colour every tick (the
// vanilla PingBehavior pattern: UnitScene.GetMinimapSprite().SetColor), and a
// HUD component draws, for every other player, a coloured dot and - when they
// are farther than playercolors.distance px from you - their name in that
// colour next to the dot, on the small minimap, on the overlay map and (from
// Module.RenderWidgets, after the window manager has drawn) on the Map tab. A
// player beyond the map's edge is pinned at the edge, so the name still shows.
//
// Settings (per machine, HWP::Settings): playercolors.palette "default" (the
// vanilla peer colours, so chat, names and waypoints agree) or "safe" (an
// Okabe-Ito palette: tells apart under deuteranopia/protanopia/tritanopia);
// playercolors.names (names on the maps, default on); playercolors.distance
// (px, default 300). hwp playercolors shows and sets them. The palette is also a row
// on the HammerwatchPlus tab (PaletteOption). colors.enabled off: no tint on the
// markers (put back to white) and no dots or names.
namespace HWP
{
	namespace PlayerColors
	{
		const string KEY_PALETTE = "playercolors.palette";
		const string KEY_NAMES = "playercolors.names";
		const string KEY_DISTANCE = "playercolors.distance";
		const int DISTANCE_DEFAULT = 300;
		const int TINT_MS = 250;
		// Okabe & Ito (2008), the usual colour-blind-safe set, peer order
		const array<string> SAFE = { "e69f00", "56b4e9", "009e73", "f0e442", "0072b2", "d55e00", "cc79a7", "ffffff" };

		string g_palette = "default";
		bool g_names = true;
		int g_distance = DISTANCE_DEFAULT;
		int g_tintTimer = 0;
		bool g_loggedTint = false;
		bool g_enabled = true;   // colors.enabled
		bool g_tinted = false;   // the markers carry our tint (turned off: made white once)
		HWPPlayerColorsHUD@ g_hud;
		BitmapFont@ g_font;
		// one cached BitmapString per peer, rebuilt when the name or colour changes
		array<BitmapString@> g_text(256);
		array<string> g_textKey(256);

		string Hex(int peer)
		{
			if (g_palette == "safe")
				return SAFE[(peer < 0 ? 0 : peer) % SAFE.length()];
			return GetPlayerColor(peer);
		}

		vec4 ColorFor(int peer) { return ParseColorRGBA("#" + Hex(peer) + "ff"); }

		void Refresh()
		{
			g_palette = HWP::Settings::GetString(KEY_PALETTE, "default");
			if (g_palette != "safe")
				g_palette = "default";
			g_enabled = HWP::Settings::GetBool("colors.enabled", true);
			g_names = HWP::Settings::GetBool("playercolors.names", true);
			g_distance = HWP::Settings::GetInt("playercolors.distance", 300);
			if (g_distance < 0)
				g_distance = 0;
			for (uint i = 0; i < g_textKey.length(); i++)
				g_textKey[i] = "";
		}

		string Status()
		{
			auto rec = GetLocalPlayerRecord();
			int peer = rec is null ? Lobby::GetLocalPeer() : int(rec.peer);
			return Resources::GetString(".hwp.colors.players.status", {
				{ "palette", g_palette }, { "peer", peer }, { "color", Hex(peer) },
				{ "names", Resources::GetString(g_names ? ".hwp.colors.players.on" : ".hwp.colors.players.off") },
				{ "distance", g_distance } });
		}

		// the player's unit on the map: the actor, or the corpse while dead
		UnitPtr MarkerUnit(PlayerRecord@ rec)
		{
			UnitPtr u;
			if (rec.actor !is null && rec.actor.m_unit.IsValid() && !rec.actor.m_unit.IsDestroyed())
				u = rec.actor.m_unit;
			else if (rec.corpse !is null && rec.corpse.m_unit.IsValid() && !rec.corpse.m_unit.IsDestroyed())
				u = rec.corpse.m_unit;
			return u;
		}

		// Tint every player's own minimap dot (players/player.inc scene "base"
		// minimap_sprite, white in vanilla). Re-applied every TINT_MS: a scene
		// change (dash, death) may bring a fresh sprite. on false: back to white.
		void TintMarkers(bool on = true)
		{
			int tinted = 0;
			for (uint i = 0; i < g_players.length(); i++)
			{
				auto rec = g_players[i];
				if (rec is null)
					continue;
				UnitPtr u = MarkerUnit(rec);
				if (!u.IsValid())
					continue;
				auto scene = u.GetCurrentUnitScene();
				if (scene is null)
					continue;
				auto ms = scene.GetMinimapSprite();
				if (ms is null)
					continue;
				ms.SetColor(on ? ColorFor(rec.peer) : vec4(1, 1, 1, 1));
				tinted++;
			}
			if (on && tinted > 0 && !g_loggedTint)
			{
				g_loggedTint = true;
				HWP::Log("colors", "player markers tinted: " + tinted + " of " + g_players.length() + " (palette " + g_palette + ")");
			}
		}

		void Tick(int ms)
		{
			g_tintTimer += ms;
			if (g_tintTimer < TINT_MS)
				return;
			g_tintTimer = 0;
			if (g_enabled || g_tinted)
				TintMarkers(g_enabled);
			g_tinted = g_enabled;
		}

		// the row on the HammerwatchPlus tab: click for the other palette
		class PaletteOption : HWP::Options::Option
		{
			string Title() override { return Resources::GetString(".hwp.colors.players.option"); }
			string Value() override { return Resources::GetString(".hwp.colors.players.palette." + g_palette); }
			void Next() override
			{
				HWP::Settings::SetString(KEY_PALETTE, g_palette == "safe" ? "default" : "safe");
				Refresh();
			}
		}

		BitmapString@ NameText(PlayerRecord@ rec, vec4 color)
		{
			if (g_font is null)
				@g_font = Resources::GetBitmapFont("gui/fonts/arial11.fnt");
			auto gm = cast<AGameplayGameMode>(g_gameMode);
			string name = gm is null ? rec.GetName() : gm.GetPlayerDisplayName(rec, false, 12);
			string key = name + "|" + Hex(rec.peer);
			uint slot = rec.peer;
			if (g_text[slot] is null || g_textKey[slot] != key)
			{
				@g_text[slot] = g_font.BuildText(name, -1, TextAlignment::Center);
				g_text[slot].SetColor(color);
				g_textKey[slot] = key;
			}
			return g_text[slot];
		}

		// One map view: where world positions land on the screen (in the
		// SpriteBatch space the caller has pushed) and the rectangle they are
		// clipped to.
		class MapView
		{
			vec2 center; // screen point of camPos
			vec2 camPos; // world position at the map's centre
			vec2 worldPerPx; // world units per screen px, x and y
			vec4 rect; // x, y, w, h of the map area
		}

		vec2 ToMap(MapView@ v, vec2 world)
		{
			return vec2(v.center.x + (world.x - v.camPos.x) / v.worldPerPx.x, v.center.y + (world.y - v.camPos.y) / v.worldPerPx.y);
		}

		// dots and names of the other players; the local player's own marker is vanilla's
		void DrawPlayers(SpriteBatch& sb, MapView@ v)
		{
			auto localRec = GetLocalPlayerRecord();
			vec2 localPos;
			bool haveLocal = false;
			if (localRec !is null)
			{
				UnitPtr lu = MarkerUnit(localRec);
				if (lu.IsValid())
				{
					localPos = xy(lu.GetPosition());
					haveLocal = true;
				}
			}
			float inset = 4;
			for (uint i = 0; i < g_players.length(); i++)
			{
				auto rec = g_players[i];
				if (rec is null || rec.local)
					continue;
				UnitPtr u = MarkerUnit(rec);
				if (!u.IsValid())
					continue;
				vec2 world = xy(u.GetPosition());
				vec2 p = ToMap(v, world);
				bool pinned = false;
				if (p.x < v.rect.x + inset) { p.x = v.rect.x + inset; pinned = true; }
				if (p.y < v.rect.y + inset) { p.y = v.rect.y + inset; pinned = true; }
				if (p.x > v.rect.x + v.rect.z - inset) { p.x = v.rect.x + v.rect.z - inset; pinned = true; }
				if (p.y > v.rect.y + v.rect.w - inset) { p.y = v.rect.y + v.rect.w - inset; pinned = true; }
				p = vec2(int(p.x), int(p.y));
				vec4 color = ColorFor(rec.peer);
				sb.FillRectangle(vec4(p.x - 3, p.y - 3, 6, 6), vec4(0, 0, 0, 0.85f));
				sb.FillRectangle(vec4(p.x - 2, p.y - 2, 4, 4), color);
				if (!g_names)
					continue;
				bool far = pinned || !haveLocal || dist(world, localPos) > float(g_distance);
				if (!far)
					continue;
				auto text = NameText(rec, color);
				float tx = p.x - text.GetWidth() / 2;
				float ty = p.y - 5 - text.GetHeight();
				// keep the label inside the map
				tx = clamp(tx, v.rect.x + 1, v.rect.x + v.rect.z - text.GetWidth() - 1);
				if (ty < v.rect.y + 1)
					ty = p.y + 5;
				sb.DrawString(vec2(int(tx), int(ty)), text);
			}
		}

		HUDMinimap@ FindMinimap(HUD@ hud)
		{
			for (uint i = 0; i < hud.m_components.length(); i++)
			{
				auto mm = cast<HUDMinimap>(hud.m_components[i]);
				if (mm !is null)
					return mm;
			}
			return null;
		}

		// The Map tab of the player menu (gui/playermenu/map.gui): drawn from
		// Module.RenderWidgets, which runs after the window manager in the same
		// SpriteBatch space, so widget origins are screen positions.
		void DrawMapTab(SpriteBatch& sb)
		{
			if (!g_enabled)
				return;
			auto gm = cast<BaseGameMode>(g_gameMode);
			if (gm is null || gm.m_windowManager is null)
				return;
			auto menu = cast<PlayerMenu>(gm.m_windowManager.GetCurrentWindow());
			if (menu is null || menu.m_tabSystem is null)
				return;
			auto tab = cast<PlayerMenuMapTab>(menu.m_tabSystem.GetCurrentTab());
			if (tab is null || tab.m_mapRect is null)
				return;
			MapView v;
			v.rect = vec4(tab.m_mapRect.m_origin.x, tab.m_mapRect.m_origin.y, tab.m_mapRect.m_width, tab.m_mapRect.m_height);
			v.center = vec2(v.rect.x + v.rect.z * 0.5f, v.rect.y + v.rect.w * 0.5f);
			v.camPos = tab.m_camPos;
			float wpp = tab.GetMapScale() * tab.m_mapViewScale;
			v.worldPerPx = vec2(wpp, wpp);
			sb.PushClipping(v.rect);
			DrawPlayers(sb, v);
			sb.PopClipping();
		}
	}
}

// Draws over the HUD minimap and the overlay map. No gui file: the base
// HUDComponent.Draw wants a widget, so Draw is replaced wholesale.
class HWPPlayerColorsHUD : HUDComponent
{
	HUDMinimap@ m_minimap;
	HUDOverlay@ m_overlay;
	bool m_looked = false;

	HWPPlayerColorsHUD(GUIBuilder@ b)
	{
		super(b, "");
	}

	void Look()
	{
		if (m_looked)
			return;
		m_looked = true;
		auto hud = GetHUD();
		if (hud is null)
			return;
		@m_minimap = HWP::PlayerColors::FindMinimap(hud);
		@m_overlay = hud.GetOverlay();
	}

	void Update(int dt, PlayerRecord@ player) override
	{
	}

	void Draw(SpriteBatch& sb, int idt) override
	{
		// playercolors.names hides the names only; DrawPlayers still draws the dots
		if (!HWP::PlayerColors::g_enabled || !GetVarBool("ui_hud_visible"))
			return;
		Look();
		auto gm = cast<BaseGameMode>(g_gameMode);
		if (gm is null)
			return;

		if (m_overlay !is null && m_overlay.m_visible)
		{
			if (CinemaManager::g_cinematicC > 0)
				return;
			// HUDOverlay.Draw: the minimap covers the window, centred on the camera,
			// prepared at (wnd + 64) * ui_overlay_minimap_scale world units and drawn
			// (wnd / m_scale + 64) px wide in the overlay's scaled space
			float s = m_overlay.m_scale <= 0.0f ? 1.0f : m_overlay.m_scale;
			vec2 wndSize = vec2(g_gameMode.m_wndWidth / s, g_gameMode.m_wndHeight / s);
			float scale = GetVarFloat("ui_overlay_minimap_scale");
			HWP::PlayerColors::MapView v;
			v.rect = vec4(0, 0, wndSize.x, wndSize.y);
			v.center = vec2(wndSize.x * 0.5f, wndSize.y * 0.5f);
			v.camPos = gm.m_camPos;
			v.worldPerPx = vec2((g_gameMode.m_wndWidth + 64) * scale / (wndSize.x + 64), (g_gameMode.m_wndHeight + 64) * scale / (wndSize.y + 64));

			mat4 tform;
			tform *= g_gameMode.m_wndInvScaleTransform;
			tform *= mat::scale(mat4(), s * g_gameMode.m_wndScale);
			sb.PushTransformation(tform);
			HWP::PlayerColors::DrawPlayers(sb, v);
			sb.PopTransformation();
			return;
		}

		if (m_minimap is null || m_minimap.m_mapRect is null || !GetVarBool("ui_minimap"))
			return;
		// HUDMinimap.Draw: the map rect, centred on the camera, GetMapScale() *
		// ui_minimap_scale world units per px, in that component's transform
		HWP::PlayerColors::MapView v;
		v.rect = vec4(m_minimap.m_mapRect.m_origin.x, m_minimap.m_mapRect.m_origin.y, m_minimap.m_mapRect.m_width, m_minimap.m_mapRect.m_height);
		v.center = vec2(v.rect.x + v.rect.z * 0.5f, v.rect.y + v.rect.w * 0.5f);
		v.camPos = gm.m_camPos;
		float wpp = m_minimap.GetMapScale() * GetVarFloat("ui_minimap_scale");
		v.worldPerPx = vec2(wpp, wpp);

		mat4 tform;
		tform *= g_gameMode.m_wndInvScaleTransform;
		tform *= mat::scale(mat4(), m_minimap.m_scale * g_gameMode.m_wndScale);
		tform *= mat::translate(mat4(), vec3(m_minimap.m_offset.x, m_minimap.m_offset.y, 0.0f));
		sb.PushTransformation(tform);
		sb.PushClipping(v.rect);
		HWP::PlayerColors::DrawPlayers(sb, v);
		sb.PopClipping();
		sb.PopTransformation();
	}
}

namespace HWPPlayerColors
{
	[Hook]
	void HUDConstructor(HUD@ hud, GUIBuilder@ b)
	{
		auto comp = HWPPlayerColorsHUD(b);
		hud.m_components.insertLast(comp); // after HUDOverlay and HUDMinimap: drawn over them
		@HWP::PlayerColors::g_hud = comp;
	}
}
