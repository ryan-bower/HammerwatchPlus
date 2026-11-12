namespace HWPFavorites
{
	void OnSettingChanged(const string &in key)
	{
		if (key == "favorites.enabled")
			HWP::Favorites::g_active = HWP::Settings::GetBool("favorites.enabled", true);
	}

	class FavoriteAction : HWP::ItemActions::KeyedAction
	{
		FavoriteAction() { super("favorites.key", 9); } // SDL F
		string Id() override { return "favorite"; }
		int Order() override { return 5; }
		string Label(Equipment::Equipment@ item) override
		{
			if (!HWP::Favorites::Enabled())
				return "";
			return Resources::GetString(HWP::Favorites::Has(item) ? ".hwp.favorites.remove" : ".hwp.favorites.add");
		}
		void Do(PlayerRecord@ record, Equipment::Equipment@ item) override
		{
			if (record.equipInventory.m_items.findByRef(item) < 0)
				return;
			HWP::Favorites::Set(item, !HWP::Favorites::Has(item));
			HWP::Log("favorites", (HWP::Favorites::Has(item) ? "favorited " : "unfavorited ") + item.GetName());
		}
	}
}

namespace Modules
{
	class HWPFavoritesModule : Module
	{
		HWPFavoritesModule()
		{
			super("hwp-favorites");
			HWPFavorites::OnSettingChanged("favorites.enabled");
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWPFavorites::OnSettingChanged));
			auto action = HWPFavorites::FavoriteAction();
			HWP::ItemActions::Register(action);
			HWP::Options::Register("favoritekey", HWP::ItemActions::ActionKeyOption(action, ".hwp.favorites.key"));
		}
	}
}
