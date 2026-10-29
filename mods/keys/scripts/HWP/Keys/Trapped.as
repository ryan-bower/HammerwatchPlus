// "The chest was trapped!!" (bugs 10.22.26 line 41). The cursed chest and
// cache (items/chests/chest_cursed.unit, cache_cursed.unit; loot tables
// chest_cursed / cache_cursed, whose main roll is prefabs/traps/cursed_chest
// or cursed_cache: shades with Aggro) look like any other chest until opened.
// HWPChest::Use calls OnChestUse before Chest::Use. The host (its own Use, or
// NetUse for a client) recognises the unit by its resource name and broadcasts
// keys.trapped with the chest position; every machine whose local player is
// within RANGE px of it shows a large announce (style hwp_trapped,
// tweak/hwp/announce_keys.sval: arial24, mid-screen, 2 s, red, trip-wire
// alert sound) and logs "[HWP:keys] trapped chest banner at x,y".
namespace HWP
{
	namespace Keys
	{
		namespace Trapped
		{
			const string EVENT = "keys.trapped";
			const string STYLE = "hwp_trapped";
			const float RANGE = 900.0f;
			int g_shown = 0;
			bool g_styleLogged = false;

			bool IsTrapped(UnitPtr unit)
			{
				if (!unit.IsValid())
					return false;
				auto prod = unit.GetUnitProducer();
				if (prod is null)
					return false;
				string name = prod.GetResourceName();
				return name.findFirst("items/chests/") == 0 && name.findFirst("cursed") >= 0;
			}

			// host side, from HWPChest::Use before the vanilla Use destroys the unit
			void OnChestUse(UnitPtr unit, PlayerBase@ player)
			{
				if (!Network::IsServer() || !HWP::Keys::g_enabled || !IsTrapped(unit))
					return;
				vec3 pos = unit.GetPosition();
				string who = (player !is null && player.m_record !is null) ? player.m_record.GetName() : "?";
				HWP::Log("keys", "trapped chest opened by " + who + " at " + int(pos.x) + "," + int(pos.y));
				SValueBuilder b;
				b.PushDictionary();
				b.PushFloat("x", pos.x);
				b.PushFloat("y", pos.y);
				b.PopDictionary();
				HWP::Net::Broadcast(EVENT, b.Build()); // runs OnTrappedEvent here too
			}

			void Register()
			{
				HWP::Net::OnEvent(EVENT, HWP::Net::EventHandler(OnTrappedEvent));
			}

			// every machine (the host included)
			void OnTrappedEvent(SValue@ data)
			{
				if (data is null)
					return;
				vec2 pos(HWP::SV::Float(data, "x", 0), HWP::SV::Float(data, "y", 0));
				auto plr = GetLocalPlayer();
				float d = -1;
				if (plr !is null && plr.m_unit.IsValid())
					d = dist(xy(plr.m_unit.GetPosition()), pos);
				if (d < 0 || d > RANGE)
				{
					HWP::Log("keys", "trapped chest at " + int(pos.x) + "," + int(pos.y) + " out of range (" + int(d) + ")");
					return;
				}
				Show();
				g_shown++;
				HWP::Log("keys", "trapped chest banner at " + int(pos.x) + "," + int(pos.y) + " (dist " + int(d) + ")");
			}

			void Show()
			{
				auto hud = GetHUD();
				if (hud is null)
					return;
				string text = Resources::GetString(".hwp.keys.trapped");
				if (HUDAnnounceStyle::Get(STYLE) !is null)
					hud.AddAnnounce(text, STYLE);
				else
				{
					// the style sval did not load: the region banner is the closest vanilla look
					if (!g_styleLogged)
					{
						g_styleLogged = true;
						HWP::LogError("keys", "announce style " + STYLE + " missing (tweak/hwp/announce_keys.sval); using region_enter");
					}
					hud.AddAnnounce(text, "", "region_enter");
					PlaySound2D(Resources::GetSoundEvent("event:/sfx/doodads/traps/trip_wire/trip_wire_alert"));
				}
			}
		}
	}
}
