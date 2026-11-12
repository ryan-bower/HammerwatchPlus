namespace HWP
{
	namespace Favorites
	{
		// The flag follows the owned object between bag, worn slots and stash.
		// SaveData writes slot + item snapshots beside vanilla data.
		bool g_active = false;

		bool Enabled() { return g_active; }
		bool Has(Item::Item@ item)
		{
			return item !is null && item.m_hwpFavorite;
		}
		bool Protected(Item::Item@ item) { return Enabled() && Has(item); }
		void Set(Equipment::Equipment@ item, bool favorite)
		{
			if (item !is null)
				item.m_hwpFavorite = favorite;
		}

		// Gear saves are nested arrays of primitives. Unknown formats do not match.
		bool Same(SValue@ a, SValue@ b)
		{
			if (a is null || b is null)
				return a is b;
			if (a.GetType() != b.GetType())
				return false;
			switch (a.GetType())
			{
				case SValueType::Integer: return a.GetInteger() == b.GetInteger();
				case SValueType::Long: return a.GetLong() == b.GetLong();
				case SValueType::Float: return a.GetFloat() == b.GetFloat();
				case SValueType::String: return a.GetString() == b.GetString();
				case SValueType::Boolean: return a.GetBoolean() == b.GetBoolean();
				case SValueType::Array:
				{
					auto aa = a.GetArray();
					auto bb = b.GetArray();
					if (aa.length() != bb.length())
						return false;
					for (uint i = 0; i < aa.length(); i++)
						if (!Same(aa[i], bb[i]))
							return false;
					return true;
				}
			}
			return false;
		}

		void SaveItems(HWP::DataBag@ bag, const string &in key, array<Equipment::Equipment@>@ items)
		{
			SValueBuilder b;
			b.PushArray();
			for (uint i = 0; i < items.length(); i++)
			{
				if (!Has(items[i]))
					continue;
				b.PushArray();
				b.PushInteger(i);
				Item::SaveItem(b, items[i]);
				b.PopArray();
			}
			b.PopArray();
			bag.Take(key, b.Build());
		}

		void LoadItems(HWP::DataBag@ bag, const string &in key, array<Equipment::Equipment@>@ items)
		{
			for (uint i = 0; i < items.length(); i++)
				Set(items[i], false);
			auto saved = bag.Get(key);
			if (saved is null || saved.GetType() != SValueType::Array)
				return;
			auto entries = saved.GetArray();
			for (uint i = 0; i < entries.length(); i++)
			{
				if (entries[i] is null || entries[i].GetType() != SValueType::Array)
					continue;
				auto entry = entries[i].GetArray();
				if (entry.length() != 2 || entry[0] is null || entry[0].GetType() != SValueType::Integer)
					continue;
				int index = entry[0].GetInteger();
				if (index < 0 || index >= int(items.length()) || items[index] is null)
					continue;
				SValueBuilder b;
				Item::SaveItem(b, items[index]);
				auto current = b.Build();
				if (Same(entry[1], current))
					Set(items[index], true);
				current.Delete();
			}
		}

		void SavePlayer(PlayerRecord@ record, HWP::DataBag@ bag)
		{
			SaveItems(bag, "favorites.bag", record.equipInventory.m_items);
			SaveItems(bag, "favorites.worn", record.equipped.m_items);
		}
		void LoadPlayer(PlayerRecord@ record, HWP::DataBag@ bag)
		{
			LoadItems(bag, "favorites.bag", record.equipInventory.m_items);
			LoadItems(bag, "favorites.worn", record.equipped.m_items);
		}
		void SaveTown(TownRecord@ town, HWP::DataBag@ bag)
		{
			for (uint i = 0; i < town.m_townStash.m_tabs.length(); i++)
				SaveItems(bag, "favorites.stash." + i, town.m_townStash.m_tabs[i].m_items);
		}
		void LoadTown(TownRecord@ town, HWP::DataBag@ bag)
		{
			for (uint i = 0; i < town.m_townStash.m_tabs.length(); i++)
				LoadItems(bag, "favorites.stash." + i, town.m_townStash.m_tabs[i].m_items);
		}
	}
}
