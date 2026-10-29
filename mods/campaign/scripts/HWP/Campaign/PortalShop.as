// The town portal's interact (doodads/hwp/forsaken_portal.unit): the vanilla mission
// board content for the hwp_campaign set. Vanilla GetItems sorts the fetched missions
// with a callback, and the engine's array sort throws "Index out of bounds" on an empty
// array, so a character the set's conditionals leave nothing for (the story intro not
// done yet) hit a script exception and no window opened (probe-portal, 2026-10-18).
// Here the portal says why instead, and the list is only sorted when it has two.
//
// Which version the portal offers (bugs 10.22.26 line 40, "portal to hoh1 in town ...
// seems to be hoh2 level"): both missions share the set, and the board listed the
// HoH2-themed hwp_forsaken_tower first (lower level span), so the top entry was the
// HoH2 version even with the HoH1 levels imported. Now the HoH1 mission
// (hwp_forsaken_tower_hoh1, tools/import_hoh1.py campaign) is the only entry whenever
// its MissionDef exists at runtime; campaign.portal_both lists both again. The log
// says which version the portal offers and which one a pick starts.
class HWPCampaignShopContent : MissionShopContent
{
	HWPCampaignShopContent(UnitPtr u, SValue& params)
	{
		super(u, params);
	}

	array<MissionDef@>@ Missions(PlayerRecord@ player)
	{
		auto missions = MissionDef::FetchMissionsFromSet(player, m_missionSetHash, m_numMissionsToShow, m_showTestMissions);
		return HWP::Campaign::PreferHoH1(missions);
	}

	void Interact(PlayerRecord@ player, int interactLevel) override
	{
		if (Missions(player).length() == 0)
		{
			if (player !is null && player.actor !is null)
				AddFloatingText(FloatingTextType::Pickup, Resources::GetString(".hwp.campaign.portal_locked"),
					player.actor.m_unit.GetPosition() + vec3(0, -24, 0));
			HWP::Log("campaign", "portal: no mission for this character (story intro not done)");
			return;
		}
		MissionShopContent::Interact(player, interactLevel);
	}

	array<IShopItem@> GetItems() override
	{
		auto missions = Missions(m_player);
		if (missions.length() > 1)
		{
			missions.sort(function(a, b){
				return a.GetLevelSpan().x < b.GetLevelSpan().x;
			});
		}
		if (m_rewardSeed == 0)
			m_rewardSeed = randi();
		array<IShopItem@> ret;
		string offered;
		for (uint i = 0; i < missions.length(); i++)
		{
			ret.insertLast(MissionShopContentItem(missions[i], m_player, m_rewardSeed + i));
			offered += (i > 0 ? ", " : "") + missions[i].m_id + " (" + HWP::Campaign::VersionName(missions[i]) + ")";
		}
		HWP::Log("campaign", "portal: offering " + offered);
		return ret;
	}

	bool Buy(const string &in func, uint hash, IShopItem@ item) override
	{
		auto shopItem = cast<MissionShopContentItem>(item);
		if (func == "pick" && shopItem !is null && shopItem.m_mission !is null)
			HWP::Log("campaign", "portal: starting " + shopItem.m_mission.m_id + " (" + HWP::Campaign::VersionName(shopItem.m_mission) + ", " + shopItem.m_mission.m_levels.length() + " floors)" + (Network::IsServer() ? "" : " - only the host can start it"));
		return MissionShopContent::Buy(func, hash, item);
	}
}

namespace HWP
{
	namespace Campaign
	{
		bool IsHoH1(MissionDef@ def)
		{
			return def !is null && def.m_id == HOH1_MISSION_ID;
		}

		string VersionName(MissionDef@ def)
		{
			return IsHoH1(def) ? "HoH1 levels" : "HoH2 themes";
		}

		// The HoH1 mission alone when it is registered (the import is packed and its
		// MissionDef loaded), else whatever the set gave. campaign.portal_both keeps both.
		array<MissionDef@>@ PreferHoH1(array<MissionDef@>@ missions)
		{
			if (missions is null || HWP::Settings::GetBool("campaign.portal_both", false))
				return missions;
			if (MissionDef::Get(HashString(HOH1_MISSION_ID)) is null)
				return missions;
			array<MissionDef@> hoh1;
			for (uint i = 0; i < missions.length(); i++)
			{
				if (IsHoH1(missions[i]))
					hoh1.insertLast(missions[i]);
			}
			// the HoH1 def exists but the set's conditionals left it out: keep the list
			if (hoh1.length() == 0)
				return missions;
			return hoh1;
		}
	}
}
