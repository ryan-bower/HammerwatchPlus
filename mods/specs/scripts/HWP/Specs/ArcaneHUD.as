// Living Mana's one bar (the user, 2026-10-25: "health and mana should truly be combined in
// the UI"). With Living Mana the pool is one number already: max mana = base mana + max health
// (ConvertStat), a hit drains mana, heals and regeneration fill it, spells spend it, and
// UpdateArcane keeps PlayerRecord.hp at the mana fraction every frame (Arcane.as). So the HUD
// shows one big blue bar with the pool's numbers where the health and mana bars were, and
// hides those two bars and their texts, for the local player while they have Living Mana;
// everyone else keeps the vanilla bars. Teammates' clients get hp and mana through the vanilla
// PlayerSyncStats (Player.as: any change over 0.001), so their co-op list (HUDCoop) shows the
// pool twice, as a full-looking health bar at the mana fraction and the mana bar: nothing to
// send. A spectated Arcane keeps the vanilla bars (the spectator's own HUD is not pooled).
//
// Drawn by a HUDComponent added after HUDPlayer (HUDConstructor hook, docs/hooks.md), not from
// HWPSpecsModule.RenderFrame: a module's RenderFrame draws before the HUD
// (AGameplayGameMode.RenderFrame: m_modules at :593, RenderWidgets at :632) and the HUD frame
// (player_info.gui "background", gui/hud.png 0 64 186 33) is opaque between its two 5 px bar
// windows, so a bar under it would show as two slits. The bar is drawn over the frame in
// HUDPlayer's own transform, at the "background" group's origin + (109, 30): the health
// window's top (bar offset 109 23, value-padding 7) to the mana window's bottom (32 + 7 + 5),
// 75 x 14 px, the mana spriteset (gui/value_bar_hori.sval variation 1) stretched to it.
namespace HWP
{
	namespace Specs
	{
		const int POOL_X = 109;   // in HUDPlayer's "background" group: the health window's top-left
		const int POOL_Y = 30;
		const int POOL_W = 75;    // the bars' width
		const int POOL_H = 14;    // the health window's top to the mana window's bottom
	}
}

class HWPSpecsPoolHUD : HUDComponent
{
	HUD@ m_hud;
	SpriteRect@ m_bar;
	BitmapFont@ m_font;
	BitmapString@ m_text;
	string m_textFor;
	bool m_shown = false;     // the vanilla bars are hidden right now

	HWPSpecsPoolHUD(GUIBuilder@ b)
	{
		super(b, "");
		@m_bar = SpriteRect("gui/value_bar_hori.sval");
		@m_font = Resources::GetBitmapFont("gui/fonts/hw8.fnt");
	}

	void DoLayout() override {}

	HUDPlayer@ Player()
	{
		for (uint i = 0; m_hud !is null && i < m_hud.m_components.length(); i++)
		{
			auto p = cast<HUDPlayer>(m_hud.m_components[i]);
			if (p !is null)
				return p;
		}
		return null;
	}

	// the shown record is the local player with Living Mana learned
	bool Pooled(PlayerRecord@ record)
	{
		if (record is null || !record.local)
			return false;
		auto plr = cast<PlayerBase>(record.actor);
		return plr !is null && HWP::Specs::Learned(plr, HWP::Specs::LIVING_MANA);
	}

	void Update(int dt, PlayerRecord@ record) override
	{
		auto hp = Player();
		if (hp is null)
			return;
		bool want = Pooled(record);
		if (want == m_shown)
			return;
		hp.m_wBarHealth.m_visible = !want;
		hp.m_wHealth.m_visible = !want;
		hp.m_wBarMana.m_visible = !want;
		hp.m_wMana.m_visible = !want;
		hp.Invalidate();
		m_shown = want;
		HWP::Specs::g_poolBar = want;
		HWP::Log("specs", want ? "living mana bar: on, health and mana bars hidden" : "living mana bar: off, vanilla bars back");
	}

	void Draw(SpriteBatch& sb, int idt) override
	{
		if (!m_shown || m_hud is null)
			return;
		auto hp = Player();
		if (hp is null || !hp.IsVisible() || !GetVarBool("ui_hud_visible"))
			return;
		PlayerRecord@ record = m_hud.m_lastRecord;
		if (record is null || hp.m_wBackground is null)
			return;

		int maxMana = max(1, record.MaxMana());
		bool dead = record.IsDead();
		float f = dead ? 0.0f : clamp(float(record.mana), 0.0f, 1.0f);
		int cur = dead ? 0 : int(floor(f * maxMana));
		string s = cur + "/" + maxMana;
		if (m_text is null || m_textFor != s)
		{
			@m_text = m_font.BuildText(s, -1, TextAlignment::Center, vec4(0.78f, 0.93f, 1.0f, 1.0f));
			m_textFor = s;
		}

		mat4 tform;
		tform *= g_gameMode.m_wndInvScaleTransform;
		tform *= mat::scale(mat4(), hp.m_scale * g_gameMode.m_wndScale);
		tform *= mat::translate(mat4(), vec3(hp.m_offset.x, hp.m_offset.y, 0.0f));
		sb.PushTransformation(tform);
		vec2 o = hp.m_wBackground.m_origin + vec2(HWP::Specs::POOL_X, HWP::Specs::POOL_Y);
		o = vec2(int(o.x), int(o.y));
		// the trough, the pool, the numbers
		sb.FillRectangle(vec4(o.x - 1, o.y - 1, HWP::Specs::POOL_W + 2, HWP::Specs::POOL_H + 2), vec4(0.02f, 0.03f, 0.06f, 1.0f));
		if (f > 0)
			m_bar.Draw(sb, o, max(2, int(HWP::Specs::POOL_W * f)), HWP::Specs::POOL_H, 1);
		if (m_text !is null)
			sb.DrawString(vec2(int(o.x + HWP::Specs::POOL_W / 2), int(o.y + (HWP::Specs::POOL_H - m_text.GetHeight()) / 2)), m_text);
		sb.PopTransformation();
	}
}

namespace HWPSpecsArcane
{
	[Hook]
	void HUDConstructor(HUD@ hud, GUIBuilder@ b)
	{
		auto comp = HWPSpecsPoolHUD(b);
		@comp.m_hud = hud;
		hud.m_components.insertLast(comp);
	}
}
