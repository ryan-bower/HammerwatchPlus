// HammerwatchPlus core: party Luck on floor rewards (HWP::Luck, mods/core/scripts/HWP/Core/
// LuckFloors.as). Every "HWP" comment marks a change from the vanilla file (.orig beside it).
namespace WorldScript
{
	enum RewardSpotQuality
	{
		Low,
		Medium,
		High
	}

	enum RewardSpotRewardType
	{
		None,
		ExpScroll,
		Material,
		Valuable,
		Trinket,
		TrinketTriPick,
		Equipment,
		Blueprint,
		ResourceCache,
		SkillSphere,
		HealthPickup,
		ManaPickup
	}

	[WorldScript color="255 228 0" icon="system/icons.png;484;324;24;24"]
	class RewardSpot
	{
		vec3 Position;

		[Editable default=true]
		bool Materials; // Gold/Wood/Stone/...

		[Editable default=true]
		bool Collectibles; // Equipment/Nlueprints/Colors/..

		[Editable default=true]
		bool Powerups; // Trinkets/Skill Spheres

		[Editable default=true]
		bool Pickups; // HP/MP/Keys/Pot charges?

		[Editable type=enum default=0]
		RewardSpotQuality Quality;

		[Editable default=false]
		bool Forced;

		[Editable default=false]
		bool Secret;

		[Editable default=false]
		bool Delayed;

		RewardSpotRewardType m_reward;
		RewardSpotQuality m_tmpAreaQuality;
		int m_tmpSortKey;

		SValue@ Save()
		{
			SValueBuilder sval;
			sval.PushInteger(int(m_reward));
			return sval.Build();
		}

		void Load(SValue@ data)
		{
			if (data.GetType() == SValueType::Integer)
				m_reward = RewardSpotRewardType(data.GetInteger());
		}

		void DebugDraw(vec2 pos, SpriteBatch& sb)
		{
			string str = "";
			
			if (Quality == RewardSpotQuality::Low)
				str = "Lo";
			else if (Quality == RewardSpotQuality::Medium)
				str = "Mid";
			else if (Quality == RewardSpotQuality::High)
				str = "Hi";
			
			if (Forced)
				str += "F";
			if (Secret)
				str += "S";
			
			auto text = Console::SysFont.BuildText(str);
			sb.DrawString(pos - vec2(text.GetWidth(), text.GetHeight() - 1) / 2, text);
		}

		SValue@ ServerExecute()
		{
			if (!Delayed)
				return null;
			
			auto gm = cast<MissionGameModeBase>(g_gameMode);
			if (gm is null)
				return null;
			
			GetWorldScript(g_scene, this).SetParamBool("Delayed", false);
			Delayed = false;
			
			SpawnReward(gm.m_missionLevel);
			return null;
		}

		int opCmp(const RewardSpot &in spot) const
		{
			if (m_tmpSortKey < spot.m_tmpSortKey)
				return -1;
			else if (m_tmpSortKey > spot.m_tmpSortKey)
				return 1;
			return 0;
		}

		bool SpawnReward(MissionLevel@ missionLevel)
		{
			float intensity = randf();
			auto mission = MissionManager::GetCurrentMission();
			if (mission !is null)
			{
				int minDiff = 10000000;
				int maxDiff = 0;
				int currDiff = 0;
				
				for (uint i = 0; i < mission.m_levels.length(); i++)
				{
					auto lvlDiff = mission.m_levels[i].m_diffLevel;
					minDiff = min(minDiff, lvlDiff);
					maxDiff = max(maxDiff, lvlDiff);
					
					if (i == MissionManager::g_module.m_missionLevelIndex)
						currDiff = lvlDiff;
				}
				
				intensity = clamp(float(currDiff - minDiff) / float(max(1, maxDiff - minDiff)), 0.0f, 1.0f);
			}
			
			if (Quality == RewardSpotQuality::Low)
				intensity = clamp(intensity - 0.25f, 0.0f, 1.0f);
			else if (Quality == RewardSpotQuality::High)
				intensity = clamp(intensity + 0.3f, 0.0f, 1.0f);

			// HWP: the party's Luck moves the quality toward the top (not a material
			// pile's amount, which reads the vanilla intensity below)
			float vanillaIntensity = intensity;
			intensity = HWP::Luck::LuckyIntensity(intensity, HWP::Luck::FloorFactor());
			
			auto gm = cast<HWR2GameMode>(g_gameMode);
			if (gm !is null)
			{
				if (m_reward == RewardSpotRewardType::Trinket && gm.HasArchitectBuff("architect_material_farmer"))
					m_reward = RewardSpotRewardType::ResourceCache;
				if (m_reward == RewardSpotRewardType::ExpScroll && gm.HasArchitectBuff("architect_material_farmer"))
					m_reward = RewardSpotRewardType::Material;
			}
			
			switch(m_reward)
			{
			
			case RewardSpotRewardType::ExpScroll:
			{
				int diffLvl = int(g_diffLevel + 0.5f) + Modifiers::lerp(ivec2(-5, 8), intensity);
				
				if (diffLvl <= 6)
					SpawnRewardUnit(Resources::GetUnitProducer("items/pickups/exp_1.unit"));
				else if (diffLvl <= 14)
					SpawnRewardUnit(Resources::GetUnitProducer("items/pickups/exp_2.unit"));
				else if (diffLvl <= 30)
					SpawnRewardUnit(Resources::GetUnitProducer("items/pickups/exp_3.unit"));
				else if (diffLvl <= 50)
					SpawnRewardUnit(Resources::GetUnitProducer("items/pickups/exp_4.unit"));
				else
					SpawnRewardUnit(Resources::GetUnitProducer("items/pickups/exp_5.unit"));
				
				break;
			}
			
			case RewardSpotRewardType::Material:
			{
				MaterialType mat = MaterialType::Gold;
				if (missionLevel.m_placedMaterialChances !is null)
				{
					ShopCost@ chances = missionLevel.m_placedMaterialChances;
					int r = randi(chances.GetTotalCost());
					for (uint i = 0; i < chances.m_cost.length(); i += 2)
					{
						r -= chances.m_cost[i + 1];
						if (r < 0)
						{
							mat = MaterialType(chances.m_cost[i]);
							break;
						}
					}
				}
				
				float amnt = 0;
				switch (mat)
				{
				case MaterialType::Gold: amnt = 75.0f; break;
				case MaterialType::Wood: amnt = 5.0f; break;
				case MaterialType::Stone: amnt = 2.5f; break;
				case MaterialType::Iron: amnt = 1.5f; break;
				case MaterialType::Ore: amnt = 1.0f; break;
				}
				
				amnt *= Modifiers::lerp(vec2(0.5f, 3.0f), vanillaIntensity); // HWP: the vanilla amount
				amnt *= 0.5f + randf();
				
				if (amnt <= 1.0f)
					amnt = 1;
				
				if (mat == MaterialType::Gold)
				{
					if (randf() < 0.66f)
						Material::DropMaterial(mat, int(amnt * lerp(0.25, 0.66f, randf())), Position + xyz(randdir()) * 6, true, false);
					if (randf() < 0.66f && amnt > 10)
						Material::DropMaterial(mat, int(amnt * lerp(0.25, 0.66f, randf())), Position + xyz(randdir()) * 8, true, false);
					if (randf() < 0.5f && amnt > 80)
						Material::DropMaterial(mat, int(amnt * lerp(0.25, 0.66f, randf())), Position + xyz(randdir()) * 10, true, false);
				}
				
				Material::DropMaterial(mat, int(amnt), Position, true, false);
				break;
			}
			
			case RewardSpotRewardType::Valuable:
			{
				vec2 span(0, 1);
				if (Quality == RewardSpotQuality::Low)
					span = vec2(0, 0.33f);
				else if (Quality == RewardSpotQuality::Medium)
					span = vec2(0.33f, 0.66f);
				else if (Quality == RewardSpotQuality::High)
					span = vec2(0.66f, 1.0f);
				
				auto valuable = missionLevel.GetValuable(Modifiers::lerp(span, intensity));
				if (valuable is null)
					PrintError("No valuables to place!");
				else
					Item::DropItem(valuable, Position, 1, false, null);
				break;
			}
			
			case RewardSpotRewardType::Trinket:
			{
				if (int(g_ngp + 0.5f) >= 1 && missionLevel.m_minNumCursedTrinkets > 0)
				{
					missionLevel.m_minNumCursedTrinkets--;
					SpawnRewardUnit(Resources::GetUnitProducer("items/chests/chest_cursed.unit"));
					break;
				}
				
				if (Quality == RewardSpotQuality::Low)
					intensity *= randf();
				else if (Quality == RewardSpotQuality::Medium)
					intensity *= Modifiers::lerp(vec2(0.33f, 1.0f), randf());
				else if (Quality == RewardSpotQuality::High)
					intensity *= Modifiers::lerp(vec2(0.66f, 1.0f), 1.0f - (randf() * randf()));
				
				if (intensity < 0.4f)
					SpawnRewardUnit(Resources::GetUnitProducer("items/chests/chest_bronze_trinket.unit"));
				else if (intensity < 0.75f)
					SpawnRewardUnit(Resources::GetUnitProducer("items/chests/chest_silver_trinket.unit"));
				else
					SpawnRewardUnit(Resources::GetUnitProducer("items/chests/chest_gold_trinket.unit"));
				break;
			}
			case RewardSpotRewardType::TrinketTriPick:
			{
				SpawnRewardUnit(Resources::GetUnitProducer("items/trinket_picker.unit"));
				break;
			}
			
			
			case RewardSpotRewardType::Equipment:
			{
				if (intensity < 0.33f)
					SpawnRewardUnit(Resources::GetUnitProducer("items/chests/chest_bronze_equipment.unit"));
				else if (intensity < 0.75f)
					SpawnRewardUnit(Resources::GetUnitProducer("items/chests/chest_silver_equipment.unit"));
				else
					SpawnRewardUnit(Resources::GetUnitProducer("items/chests/chest_gold_equipment.unit"));
				break;
			}
			
			case RewardSpotRewardType::Blueprint:
			{
				BlueprintBehavior::SpawnBlueprint(xy(Position));
				break;
			}
			
			case RewardSpotRewardType::ResourceCache:
			{
				if (int(g_ngp + 0.5f) >= 1 && missionLevel.m_minNumCursedResCaches > 0)
				{
					missionLevel.m_minNumCursedResCaches--;
					SpawnRewardUnit(Resources::GetUnitProducer("items/chests/cache_cursed.unit"));
					break;
				}
				
				if (intensity < 0.4f)
					SpawnRewardUnit(Resources::GetUnitProducer("items/chests/cache_bronze.unit"));
				else if (intensity < 0.75f)
					SpawnRewardUnit(Resources::GetUnitProducer("items/chests/cache_silver.unit"));
				else
					SpawnRewardUnit(Resources::GetUnitProducer("items/chests/cache_gold.unit"));
				break;
			}
			
			case RewardSpotRewardType::HealthPickup:
			{
				if (intensity < 0.25f)
					SpawnRewardUnit(Resources::GetUnitProducer("items/pickups/health_apple.unit"));
				else if (intensity < 0.5f)
					SpawnRewardUnit(Resources::GetUnitProducer("items/pickups/health_orange.unit"));
				else if (intensity < 0.75f)
					SpawnRewardUnit(Resources::GetUnitProducer("items/pickups/health_fish.unit"));
				else
					SpawnRewardUnit(Resources::GetUnitProducer("items/pickups/health_meat.unit"));
				break;
			}
			
			case RewardSpotRewardType::ManaPickup:
			{
				if (intensity < 0.25f)
					SpawnRewardUnit(Resources::GetUnitProducer("items/pickups/mana_shard.unit"));
				else if (intensity < 0.5f)
					SpawnRewardUnit(Resources::GetUnitProducer("items/pickups/mana_shard_big.unit"));
				else if (intensity < 0.75f)
					SpawnRewardUnit(Resources::GetUnitProducer("items/pickups/mana_pyramid.unit"));
				else
					SpawnRewardUnit(Resources::GetUnitProducer("items/pickups/mana_sphere.unit"));
				break;
			}
			
			case RewardSpotRewardType::SkillSphere:
			{
				SpawnRewardUnit(Resources::GetUnitProducer("items/skill_sphere.unit"));
				break;
			}
			
			case RewardSpotRewardType::None:
			default:
			}
			
			m_reward = RewardSpotRewardType::None;
			return true;
		}

		bool SpawnRewardUnit(UnitProducer@ prod)
		{
			if (prod is null)
				return false;
			prod.Produce(g_scene, Position);
			return true;
		}
	}
	
	
	[WorldScript color="140 255 120" icon="system/icons.png;484;324;24;24"]
	class RewardSpotModifierArea
	{
		vec3 Position;

		[Editable type=enum default=1]
		RewardSpotQuality Quality;

		[Editable default=128]
		int Range;

		int m_tmpRangeSq;

		void DebugDraw(vec2 pos, SpriteBatch& sb)
		{
			sb.DrawCircle(pos, Range, vec4(140, 255, 120, 255) / 255.0f, 25);
		}
	}
}

namespace RewardSpot
{
	WorldScript::RewardSpotQuality min(WorldScript::RewardSpotQuality a, WorldScript::RewardSpotQuality b)
	{
		if (int(a) < int(b))
			return a;
		return b;
	}


	bool FilterRewardSpot(WorldScript::RewardSpot@ spot, WorldScript::RewardSpotRewardType rewardType)
	{
		switch(rewardType)
		{
		case WorldScript::RewardSpotRewardType::ExpScroll:
			break;
		case WorldScript::RewardSpotRewardType::Material:
			break;
		case WorldScript::RewardSpotRewardType::Valuable:
			break;
		case WorldScript::RewardSpotRewardType::Trinket:
			break;
		case WorldScript::RewardSpotRewardType::TrinketTriPick:
			break;
		case WorldScript::RewardSpotRewardType::Equipment:
			break;
		case WorldScript::RewardSpotRewardType::Blueprint:
		{
			if (spot.Forced)
				return false;
			break;
		}
		case WorldScript::RewardSpotRewardType::ResourceCache:
			break;
		case WorldScript::RewardSpotRewardType::HealthPickup:
			break;
		case WorldScript::RewardSpotRewardType::ManaPickup:
			break;
		case WorldScript::RewardSpotRewardType::SkillSphere:
		{
			if (spot.Delayed || spot.Secret)
				return false;
			break;
		}
		case WorldScript::RewardSpotRewardType::None:
		default:
			//return false;
		}
		
		return true;
	}

	bool AssignReward(array<WorldScript::RewardSpot@>@ spots, WorldScript::RewardSpotRewardType rewardType)
	{
		for (uint i = 0; i < spots.length(); i++)
		{
			auto spot = spots[i];
			if (!FilterRewardSpot(spot, rewardType))
				continue;
			
			spot.m_reward = rewardType;
			spots.removeAt(i);
			return true;
		}
		
		return false;
	}

	void SpawnRewards(MissionLevel@ missionLevel)
	{
		if (!Network::IsServer() || missionLevel is null)
			return;

		print("RewardSpot::SpawnRewards");

		array<WorldScript::RewardSpotModifierArea@> spotAreas;
		array<WorldScript::RewardSpot@> spots;
		
		int numPossibleMats = 0;
		int numPossiblePickups = 0;
		
		{
			auto res = g_scene.FetchAllWorldScripts("RewardSpotModifierArea");
			for (uint i = 0; i < res.length(); i++)
			{
				auto script = res[i];
				if (!script.IsEnabled())
					continue;
				
				auto spotArea = cast<WorldScript::RewardSpotModifierArea>(script.GetUnit().GetScriptBehavior());
				if (spotArea is null)
					continue;
				
				spotArea.m_tmpRangeSq = spotArea.Range * spotArea.Range;
				spotAreas.insertLast(spotArea);
			}
		}
		
		{
			auto res = g_scene.FetchAllWorldScripts("RewardSpot");
			print("RewardSpot::RewardSpot: " + res.length());
			
			for (uint i = 0; i < res.length(); i++)
			{
				auto script = res[i];
				if (!script.IsEnabled())
					continue;
				
				auto unit = script.GetUnit();
				auto spot = cast<WorldScript::RewardSpot>(unit.GetScriptBehavior());
				if (spot is null)
					continue;
				
				spot.m_tmpAreaQuality = WorldScript::RewardSpotQuality::Medium;
				for (uint j = 0; j < spotAreas.length(); j++)
				{
					auto spotArea = spotAreas[j];
					if (distsq(spotArea.Position, unit) > spotArea.m_tmpRangeSq)
						continue;
					
					spot.Quality = min(spot.Quality, spotArea.Quality);
					spot.m_tmpAreaQuality = spotArea.Quality;
					break;
				}
				
				spot.m_tmpSortKey = 10 * int(spot.Quality) + 4 * int(spot.m_tmpAreaQuality) + (spot.Forced ? 100000 : 0);
				spots.insertAt(randi(spots.length()), spot);
				
				if (spot.Materials)
					numPossibleMats++;
				if (spot.Pickups)
					numPossiblePickups++;
			}
		}
		
		spots.sortDesc();
		array<WorldScript::RewardSpot@> allSpots = spots;

		// HWP: the party's Luck leans each count below toward its maximum (LuckyRandf, never
		// past the vanilla range) and multiplies the blueprint chance; skill spheres and
		// material piles stay vanilla
		float luck = HWP::Luck::FloorFactor();
		
		int numSkillSpheres = roll_round(Modifiers::lerp(missionLevel.m_minNumSkillSpheres, randf()));
		for (int i = 0; i < numSkillSpheres; i++)
			AssignReward(spots, WorldScript::RewardSpotRewardType::SkillSphere);
		
		float blueprintChance = HWP::Luck::Chance(0.25f, luck); // HWP
		int numBlueprints = roll_round(blueprintChance);
		if (numBlueprints > 0)
		{
			if (g_scalars.IsSet("blueprint_cooldown"))
				numBlueprints = 0;
			else
				g_scalars.SetCD(HashString("blueprint_cooldown"), 2);
		}
		
		for (int i = 0; i < numBlueprints; i++)
			AssignReward(spots, WorldScript::RewardSpotRewardType::Blueprint);
		
		
		
		int numTrinketTripicks = roll_round(Modifiers::lerp(missionLevel.m_NumTrinketTriPicks, HWP::Luck::LuckyRandf(luck)));
		for (int i = 0; i < numTrinketTripicks; i++)
			AssignReward(spots, WorldScript::RewardSpotRewardType::TrinketTriPick);
		
		int numTrinkets = roll_round(Modifiers::lerp(missionLevel.m_minNumTrinkets, HWP::Luck::LuckyRandf(luck)));
		for (int i = 0; i < numTrinkets; i++)
			AssignReward(spots, WorldScript::RewardSpotRewardType::Trinket);
		
		int numEquipment = roll_round(Modifiers::lerp(missionLevel.m_minNumEquipment, HWP::Luck::LuckyRandf(luck)));
		for (int i = 0; i < numEquipment; i++)
			AssignReward(spots, WorldScript::RewardSpotRewardType::Equipment);
		
		int numResCaches = roll_round(Modifiers::lerp(missionLevel.m_minNumResCaches, HWP::Luck::LuckyRandf(luck)));
		for (int i = 0; i < numResCaches; i++)
			AssignReward(spots, WorldScript::RewardSpotRewardType::ResourceCache);
		
		int numExpScrolls = roll_round(Modifiers::lerp(vec2(1.0f, 2.0f), HWP::Luck::LuckyRandf(luck)));
		for (int i = 0; i < numExpScrolls; i++)
			AssignReward(spots, WorldScript::RewardSpotRewardType::ExpScroll);
		
		int numValuables = roll_round(Modifiers::lerp(vec2(2.0f, 4.0f), HWP::Luck::LuckyRandf(luck)));
		for (int i = 0; i < numValuables; i++)
			AssignReward(spots, WorldScript::RewardSpotRewardType::Valuable);
		
		int numMats = int(numPossibleMats * (0.15f + 0.1f * randf()));
		for (int i = 0; i < numMats; i++)
			AssignReward(spots, WorldScript::RewardSpotRewardType::Material);
		
		int numHPPickups = int(numPossiblePickups * (0.15f + 0.1f * HWP::Luck::LuckyRandf(luck)));
		for (int i = 0; i < numHPPickups; i++)
			AssignReward(spots, WorldScript::RewardSpotRewardType::HealthPickup);
		
		int numMPPickups = int(numPossiblePickups * (0.25f + 0.1f * HWP::Luck::LuckyRandf(luck)));

		HWP::Log("luck", "floor rewards at party Luck x" + HWP::Luck::Fmt(luck) + ": blueprint chance "
			+ int(blueprintChance * 100.0f + 0.5f) + "% -> " + numBlueprints + ", trinket picks " + numTrinketTripicks
			+ ", trinkets " + numTrinkets + ", equipment " + numEquipment + ", caches " + numResCaches + ", scrolls "
			+ numExpScrolls + ", valuables " + numValuables + ", health " + numHPPickups + " and mana " + numMPPickups
			+ " of " + numPossiblePickups + " pickup spots");
		for (int i = 0; i < numMPPickups; i++)
			AssignReward(spots, WorldScript::RewardSpotRewardType::ManaPickup);
		
		for (uint i = 0; i < allSpots.length(); i++)
		{
			if (!allSpots[i].Forced || allSpots[i].m_reward != WorldScript::RewardSpotRewardType::None)
				continue;
			allSpots[i].m_reward = WorldScript::RewardSpotRewardType::ResourceCache;
		}
		
		for (uint i = 0; i < allSpots.length(); i++)
		{
			if (allSpots[i].Delayed || allSpots[i].m_reward == WorldScript::RewardSpotRewardType::None)
				continue;
			allSpots[i].SpawnReward(missionLevel);
		}
	}

}