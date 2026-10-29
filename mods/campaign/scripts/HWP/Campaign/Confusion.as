// Confusion (bugs 10.22.26 line 28, "bring back confusion"). HoH2 keeps the engine side
// of HoH1's confusion: an ActorBuffDef with confuse=true inverts the player's move and aim
// input (Player.as, m_buffs.Confuse()), and tweak/buffs/status_effects.sval:confusion
// exists, but no HoH2 enemy or trap applies it (only player gear does). HoH1 applied it
// from eye-type enemies (the floating eyes' gaze) and from confusion traps, so this module
// brings both back: the Dark Halls eyes (actors/aberrations/eyes/) confuse the player they
// hit with a chance, the campaign's imported HoH1 eyes and bats apply their own HoH1 buff,
// and the confusion glyph trap (Traps.as) applies the trap buff. The buffs are ours
// (tweak/hwp/campaign_buffs.sval: HoH1's 2500 ms gaze and 1000 ms trap, the vanilla
// confusion icon), a purple screen tint shows while confused, and `hwp campaign confuse
// [ms]` applies it for testing. Setting campaign.confusion (default on) gates the enemy
// and trap sources; campaign.confusion_eye_chance is the eye hit chance in percent.
namespace HWP
{
	namespace Campaign
	{
		namespace Confusion
		{
			const string BUFF = "tweak/hwp/campaign_buffs.sval:hwp_confusion";
			const string TRAP_BUFF = "tweak/hwp/campaign_buffs.sval:hwp_trap_confusion";
			const string EYE_PATH = "actors/aberrations/eyes/";

			bool g_enabled = true;
			int g_eyeChance = 35;
			bool g_warned = false;
			ActorBuffDef@ g_def;

			void RefreshSettings()
			{
				// campaign.enabled off (the settings page's switch) turns it off with the rest
				g_enabled = HWP::Settings::GetBool("campaign.enabled", true) && HWP::Settings::GetBool("campaign.confusion", true);
				g_eyeChance = clamp(HWP::Settings::GetInt("campaign.confusion_eye_chance", 35), 0, 100);
			}

			ActorBuffDef@ Def()
			{
				if (g_def is null)
					@g_def = LoadActorBuff(BUFF);
				if (g_def is null && !g_warned)
				{
					g_warned = true;
					HWP::LogError("campaign", "confusion: buff " + BUFF + " not found");
				}
				return g_def;
			}

			bool Confused(Player@ plr)
			{
				return plr !is null && plr.m_buffs.Confuse();
			}

			// A buff on a Player is owned by that player's machine (the vanilla ApplyBuff
			// effects run on the victim's side too), so this applies on whoever calls it.
			bool Apply(Player@ plr, int ms, const string &in why)
			{
				auto def = Def();
				if (def is null || plr is null)
					return false;
				plr.ApplyBuff(ActorBuff(plr, def, 1.0f, false, 0, ms));
				HWP::Log("campaign", "confusion: " + why + " confused the player for " + (ms > 0 ? ms : def.m_duration) + " ms");
				return true;
			}

			// [Hook] PlayerDamageTaken: an eye's hit confuses with a chance
			void OnDamage(Player@ player, DamageInfo@ dmg)
			{
				if (!g_enabled || player is null || dmg is null || dmg.Attacker is null || dmg.Damage <= 0)
					return;
				if (!dmg.Attacker.m_unit.IsValid())
					return;
				string path = dmg.Attacker.m_unit.GetDebugName();
				if (path.findFirst(EYE_PATH) < 0)
					return;
				if (player.m_buffs.Confuse())
					return;
				if (randi(100) >= g_eyeChance)
					return;
				Apply(player, -1, path);
			}

			// hwp campaign confuse [ms]: the local player, cheats on
			void Cheat(array<string>@ args)
			{
				if (!HWP::Cheats::On())
					return;
				auto plr = GetLocalPlayer();
				if (plr is null)
				{
					HWP::Commands::Reply("no player in the world");
					return;
				}
				int ms = HWP::Cheats::IntArg(args, 1, -1);
				if (Apply(plr, ms, "hwp campaign confuse"))
					HWP::Commands::Reply("confused for " + (ms > 0 ? ms : Def().m_duration) + " ms (" + BUFF + ")");
				else
					HWP::Commands::Reply("confusion buff missing - check the log");
			}
		}
	}
}

// A purple pulse over the whole window while the local player is confused: HoH1 had a
// wobbling screen; HoH2 inverts the input silently, which reads as a bug without a cue.
class HWPCampaignConfusionHUD : HUDComponent
{
	int m_time = 0;

	HWPCampaignConfusionHUD(GUIBuilder@ b)
	{
		super(b, "");
		m_drawOnTop = true;
	}

	void DoLayout() override {}

	void Update(int dt, PlayerRecord@ record) override
	{
		HUDComponent::Update(dt, record);
		m_time += dt;
	}

	void Draw(SpriteBatch& sb, int idt) override
	{
		if (!GetVarBool("ui_hud_visible"))
			return;
		auto plr = GetLocalPlayer();
		if (!HWP::Campaign::Confusion::Confused(plr))
			return;
		float pulse = 0.5f + 0.5f * sin(m_time / 180.0f);
		float a = 0.10f + 0.12f * pulse;
		// bigger than any window in any HUD scale; no transform needed
		sb.FillRectangle(vec4(-4096, -4096, 8192, 8192), vec4(0.45f, 0.10f, 0.60f, a));
	}
}

namespace HWPCampaignHooks
{
	[Hook]
	void PlayerDamageTaken(Player@ player, DamageInfo@ dmg)
	{
		HWP::Campaign::Confusion::OnDamage(player, dmg);
	}

	[Hook]
	void HUDConstructor(HUD@ hud, GUIBuilder@ b)
	{
		hud.m_components.insertLast(HWPCampaignConfusionHUD(b));
	}
}
