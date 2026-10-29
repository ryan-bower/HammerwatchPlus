// The tavern's only module: it makes tavern.* host-synced, so in a lobby the host's
// tavern.enabled decides the food and drink slots (Missions/MissionFoods.as reads it).
namespace Modules
{
	class HWPTavernModule : Module
	{
		HWPTavernModule()
		{
			super("hwp-tavern");
			HWP::Settings::Sync("tavern.");
		}
	}
}
