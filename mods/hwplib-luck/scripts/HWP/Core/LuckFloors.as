// HWP::Luck on generated floors: the party's average Luck (FloorLuck) as each floor is made.
// - Secret rooms: a chance of one more than the theme's "*_secrets" SpawnPrefabSet allows
//   (keep_secrets max 1, barracks_secrets max 2, ...); the room still needs a spot its
//   pattern matches (HWPLuckSecretSpawn below).
// - The imp: its room's "*_imp" SpawnPrefabSet (exec-chance 0.1 in every theme that has one)
//   runs at that chance times the factor (HWPLuckChanceSpawn below).
// - Reward spots (core's WorldScript/RewardSpot.as override): every count rolled between a
//   floor's vanilla minimum and maximum leans to the maximum (LuckyRandf), the blueprint
//   chance is multiplied (Chance), and each spot's quality (the vanilla intensity that picks
//   food / mana / chest / cache / scroll / valuable tiers) moves toward the top
//   (LuckyIntensity). Skill spheres and material piles stay vanilla.
// - Blueprints (core's BlueprintBank.as override): the food, drink, enchantment and trinket
//   recipe picks weigh the rarer qualities up (PickByQuality, the RollPool rule).
// - Fishing holes (fishing module): the run chance is multiplied.
// - Keys (keys module): the floor's key budget share is multiplied (still at most 95 % of
//   the locked chests), the budget's tier pick weighs the higher tiers up, and a gold
//   chest's ace chance is multiplied (at most ACE_CAP).
//
// A floor is generated in its own script context (the next one preloads while the current
// one runs, docs/RE_NOTES.md), where the lobby's records are not loaded. The host keeps the
// party's average Luck in the run scalar PARTY_SCALAR (KeepPartyScalar in Luck.as), which the
// level's save carries into generation and the level (AGameplayGameMode.LoadFlags loads the
// scalars), so the Luck counted is the party's as of the save the floor came from.
//
// A roll every machine makes alike (a chest's ace lock, from a hash) needs the same value on
// every machine: the host broadcasts its floor value (FLOOR_EVENT, every FLOOR_EVERY_MS), a
// client uses it once it came, and FloorReady() tells such a roll to wait for it.
namespace HWP
{
	namespace Luck
	{
		const string PARTY_SCALAR = "hwp_luck_party";
		const float SECRET_PER_FACTOR = 0.5f;   // extra room chance per +1.0 of factor
		const float SECRET_CAP = 0.75f;
		const float ACE_CAP = 0.5f;             // a gold chest's ace chance with Luck
		const string FLOOR_EVENT = "hwp.luck.floor";
		const int FLOOR_EVERY_MS = 3000;

		// The floor's own value, taken on its first frame before the host refreshes the
		// scalar for the next floor: rolls made after the start (the fishing hole, a delayed
		// reward spot, a blueprint unit) count the same Luck as the generation did.
		bool g_floorSnapped = false;
		bool g_floorHasScalar = false;
		float g_floorScalar = 0;

		void SnapFloorLuck()
		{
			if (g_floorSnapped)
				return;
			g_floorSnapped = true;
			g_floorHasScalar = g_scalars.IsSet(PARTY_SCALAR);
			g_floorScalar = g_floorHasScalar ? g_scalars.Get(PARTY_SCALAR) : 0.0f;
		}

		// the party's average Luck for a floor: the scalar the level's save carried (its
		// first-frame value once taken), else the lobby as this machine sees it (a client
		// without the scalar, a context with no records)
		float FloorLuck()
		{
			if (!Network::IsServer() && g_floorFromHost)
				return g_floorHostLuck;
			if (g_floorSnapped)
				return g_floorHasScalar ? g_floorScalar : PartyLuck();
			if (g_scalars.IsSet(PARTY_SCALAR))
				return g_scalars.Get(PARTY_SCALAR);
			return PartyLuck();
		}

		float FloorFactor() { return FactorOf(FloorLuck()); }

		// the host's floor value on a client (a fresh context per floor, so it is this floor's)
		bool g_floorFromHost = false;
		float g_floorHostLuck = 0;
		int g_floorTimer = FLOOR_EVERY_MS;

		void OnFloorEvent(SValue@ data)
		{
			if (Network::IsServer())
				return;
			g_floorHostLuck = HWP::SV::Float(data, "luck");
			if (!g_floorFromHost)
				HWP::Log("luck", "floor Luck from the host: " + Fmt(g_floorHostLuck));
			g_floorFromHost = true;
		}

		// every peer, from the module's UpdateFrame: the host sends its floor value
		void FloorTick(int ms)
		{
			SnapFloorLuck();
			if (!Network::IsServer())
				return;
			g_floorTimer += ms;
			if (g_floorTimer < FLOOR_EVERY_MS)
				return;
			g_floorTimer = 0;
			SValueBuilder b;
			b.PushDictionary();
			b.PushFloat("luck", FloorLuck());
			b.PopDictionary();
			HWP::Net::Broadcast(FLOOR_EVENT, b.Build());
		}

		// true once this machine has the floor value every machine agrees on
		bool FloorReady() { return Network::IsServer() || g_floorFromHost; }

		// a gold chest's chance to be an ace chest: the base times the factor, at most
		// ACE_CAP (or the base, when the setting is higher)
		float AceChance(float base, float factor) { return min(Chance(base, factor), max(base, ACE_CAP)); }

		// the chance of one more secret room: 50 % per +1.0 of factor, at most 75 %
		float SecretRoomChance(float factor) { return clamp((factor - 1.0f) * SECRET_PER_FACTOR, 0.0f, SECRET_CAP); }

		// randf() leaning to 1 with luck: 1 - (1 - u)^factor. Uniform at factor 1; at
		// factor 2 the mean goes from 0.5 to 0.67. Never leaves 0..1, so a count rolled
		// with it stays within the vanilla range.
		float LuckyRandf(float factor)
		{
			float u = randf();
			if (factor <= 1.0f)
				return u;
			return 1.0f - pow(1.0f - u, factor);
		}

		// a reward quality 0..1 moved toward 1: the gap to the top divided by the factor
		// (factor 2 halves it: 0.5 becomes 0.75)
		float LuckyIntensity(float intensity, float factor)
		{
			if (factor <= 1.0f)
				return intensity;
			return clamp(1.0f - (1.0f - intensity) / factor, 0.0f, 1.0f);
		}

		// An index into candidates by their qualities: every candidate rarer than the
		// commonest quality among them weighs factor, the rest 1 (the RollPool rule).
		// Uniform at factor 1, as vanilla's randi(n). -1 for none.
		int PickByQuality(array<int>@ qualities, float factor)
		{
			uint n = qualities.length();
			if (n == 0)
				return -1;
			int lowest = qualities[0];
			for (uint i = 1; i < n; i++)
				lowest = min(lowest, qualities[i]);
			float sum = 0;
			for (uint i = 0; i < n; i++)
				sum += qualities[i] > lowest ? factor : 1.0f;
			float r = randf() * sum;
			for (uint i = 0; i < n; i++)
			{
				r -= qualities[i] > lowest ? factor : 1.0f;
				if (r < 0)
					return int(i);
			}
			return int(n - 1);
		}

		// " (blueprint <kind> of <n> at x<f>: <quality>)" for the blueprint factories
		void LogBlueprint(const string &in kind, uint n, int quality, float factor)
		{
			HWP::Log("luck", "blueprint " + kind + " picked of " + n + " at x" + Fmt(factor) + ": quality " + quality);
		}

		bool EndsWith(const string &in s, const string &in suffix)
		{
			return s.length() >= suffix.length() && s.substr(s.length() - suffix.length()) == suffix;
		}

		// From the module constructor (every level load and every preload, before
		// generation); idempotent. Swaps each "*_secrets" SpawnPrefabSet for the Luck one
		// and each "*_imp" one for the Luck chance one; imps counts the latter.
		int InstallSecrets(int &out imps)
		{
			int swapped = 0;
			imps = 0;
			for (uint i = 0; i < MissionDef::Instances.length(); i++)
			{
				auto mission = MissionDef::Instances[i];
				for (uint j = 0; j < mission.m_levels.length(); j++)
				{
					auto gen = cast<DungeonGenerator>(mission.m_levels[j].m_generator);
					if (gen is null)
						continue;
					for (uint k = 0; k < gen.m_genCommands.length(); k++)
					{
						auto spawn = cast<SpawnPrefabSet>(gen.m_genCommands[k]);
						if (spawn is null || cast<HWPLuckSecretSpawn>(spawn) !is null || cast<HWPLuckChanceSpawn>(spawn) !is null)
							continue;
						if (EndsWith(spawn.m_set, "_secrets"))
						{
							@gen.m_genCommands[k] = HWPLuckSecretSpawn(spawn);
							swapped++;
						}
						else if (EndsWith(spawn.m_set, "_imp") && spawn.m_execChance < 1.0f)
						{
							@gen.m_genCommands[k] = HWPLuckChanceSpawn(spawn);
							imps++;
						}
					}
				}
			}
			return swapped;
		}
	}
}

class HWPLuckSecretSpawn : SpawnPrefabSet
{
	HWPLuckSecretSpawn(SpawnPrefabSet@ from)
	{
		m_execChance = from.m_execChance;
		@m_conditionals = from.m_conditionals;
		m_set = from.m_set;
		m_min = from.m_min;
		m_max = from.m_max;
		m_numIters = from.m_numIters;
		m_numBoost = from.m_numBoost;
		m_typeMinLimit = from.m_typeMinLimit;
	}

	bool Execute(DungeonBrush@ brush, PrefabPlacement@ pfbPlacer) override
	{
		float luck = HWP::Luck::FloorLuck();
		float chance = HWP::Luck::SecretRoomChance(HWP::Luck::FactorOf(luck));
		bool extra = chance > 0 && randf() < chance;
		int vanillaMax = m_max;
		if (extra)
			m_max++;
		uint pois = brush.m_pointsOfInterest.length();
		bool ok = SpawnPrefabSet::Execute(brush, pfbPlacer);
		int placed = int(brush.m_pointsOfInterest.length() - pois);
		m_max = vanillaMax;
		auto gm = cast<MissionGameModeBase>(g_gameMode);
		string level = (gm is null || gm.m_missionLevel is null) ? "" : " on " + gm.m_missionLevel.m_id;
		HWP::Log("luck", "secrets " + m_set + level + ": party Luck " + int(luck + (luck < 0 ? -0.5f : 0.5f))
			+ ", extra room chance " + int(chance * 100.0f + 0.5f) + "%: " + (extra ? "rolled" : "not rolled")
			+ ", max " + (vanillaMax + (extra ? 1 : 0)) + ", placed " + placed);
		return ok;
	}
}

// A SpawnPrefabSet that runs at its vanilla exec-chance times the party's floor factor (the
// generator rolls m_execChance before Execute, so this one sets it to 1 and rolls itself).
class HWPLuckChanceSpawn : SpawnPrefabSet
{
	float m_vanillaChance;

	HWPLuckChanceSpawn(SpawnPrefabSet@ from)
	{
		m_vanillaChance = from.m_execChance;
		m_execChance = 1.0f;
		@m_conditionals = from.m_conditionals;
		m_set = from.m_set;
		m_min = from.m_min;
		m_max = from.m_max;
		m_numIters = from.m_numIters;
		m_numBoost = from.m_numBoost;
		m_typeMinLimit = from.m_typeMinLimit;
	}

	bool Execute(DungeonBrush@ brush, PrefabPlacement@ pfbPlacer) override
	{
		float luck = HWP::Luck::FloorLuck();
		float chance = HWP::Luck::Chance(m_vanillaChance, HWP::Luck::FactorOf(luck));
		bool rolled = randf() < chance;
		uint pois = brush.m_pointsOfInterest.length();
		bool ok = !rolled || SpawnPrefabSet::Execute(brush, pfbPlacer);
		int placed = int(brush.m_pointsOfInterest.length() - pois);
		auto gm = cast<MissionGameModeBase>(g_gameMode);
		string level = (gm is null || gm.m_missionLevel is null) ? "" : " on " + gm.m_missionLevel.m_id;
		HWP::Log("luck", "chance set " + m_set + level + ": party Luck " + int(luck + (luck < 0 ? -0.5f : 0.5f))
			+ ", chance " + int(chance * 100.0f + 0.5f) + "% (" + int(m_vanillaChance * 100.0f + 0.5f) + "% vanilla): "
			+ (rolled ? "rolled" : "not rolled") + ", placed " + placed);
		return ok;
	}
}
