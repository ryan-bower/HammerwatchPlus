// Joints. A Holy Herb is rolled into an item from the materials tab (Plants & Herbs: click a
// herb, "Roll J?" -> "Huzzah!"; RollJoint). An item saves only its base item, quality, level
// and mods, so the puffs left are the base item: hwp_joint_<strain>_<n>, n = 5..1
// (tweak/hwp/equipment_joints.sval), each with its own icon and model (hwp_joint_<n>.model
// rides the left hand; the twin's hwp_joint_mh_<n>.model is the same mesh on the right hand,
// as Firearms' hwp_glock_oh is its hwp_glock_mh).
//
// - Two hands: a rolled joint is an off-hand item. Its main-hand twin is hwp_joint_mh_<strain>_<n>
//   (the same item in the main-hand slot, as Firearms' pistols): a joint clicked in the bag
//   while the off hand already holds a joint becomes its twin first (core's HWP::Bag::OnEquip,
//   JointEquip) and so lands in the main hand; a twin back in the bag turns into the off-hand
//   joint again (UpdateTwins). `hwp joint wield main|off` puts the newest bag joint in a hand.
//   Right click puffs the off-hand joint (its off-hand skill), left click the main-hand one
//   (hwp_joint_puff_mh, players/hwp/farming/attacks_joint.sval); each has its own puffs, and
//   the two herbs are two mission buffs at once (FarmingModule.as ApplyHerb: slot hwp_herb for
//   the off hand, hwp_herb2 for the main hand; the same strain in both hands refreshes one).
// - Held, it smoulders: the item re-applies a buff whose fx is a thin wisp.
// - A puff: at the cast point HWPJointPuff runs on every machine: the tip turns cherry red
//   for LIT_MS (the _lit model, swapped into the item's cached model the way Firearms'
//   HeldModel.as swaps a gun in) and a haze is left: one bank in a run or a town building,
//   HOTBOX_BANKS banks around the smoker outdoors in town, where no walls hold it (hotboxing
//   the square). Hazes thin out over a minute; puffs stack. On the smoker's machine it also
//   gives the strain's buff for HERB_FLOORS floors and, once the tip cools, burns that hand's
//   joint down a stage; the last puff uses it up.
// - Someone with a free off hand next to a player holding a joint (either hand) takes it
//   with the interact key, no questions asked (the host relays: JOINT_TAKE -> JOINT_HAND ->
//   JOINT_GIVE -> JOINT_GET); it arrives as an off-hand joint.
namespace HWP
{
	namespace Farming
	{
		const int JOINT_USES = 5;
		const int LIT_MS = 1500;
		const float TAKE_RANGE = 26.0f;
		const string JOINT_PREFIX = "hwp_joint_";       // off hand: hwp_joint_<strain>_<n>
		const string JOINT_MH_PREFIX = "hwp_joint_mh_"; // main-hand twin: hwp_joint_mh_<strain>_<n>
		const string LIT_MODEL = "players/models/equipment/hwp_joint_%n%_lit.model";       // rides the left hand
		const string LIT_MODEL_MH = "players/models/equipment/hwp_joint_mh_%n%_lit.model"; // the twin: the right hand
		const string HAZE_FX = "effects/hwp/joint_haze.effect";
		const int HOTBOX_BANKS = 4;         // town outdoors: haze banks a puff leaves around the smoker
		const float HOTBOX_RADIUS = 70.0f;  // how far out the outer banks stand
		const string JOINT_TAKE = "farm.joint_take"; // taker -> host: { holder }
		const string JOINT_HAND = "farm.joint_hand"; // host -> holder: { taker }
		const string JOINT_GIVE = "farm.joint_give"; // holder -> host: { taker, id }
		const string JOINT_GET = "farm.joint_get";   // host -> taker: { id }

		int g_rolled = 0;
		int g_puffs = 0;
		int g_hazes = 0;
		int g_taken = 0;
		int g_given = 0;
		array<UnitPtr> g_hazeUnits; // the haze effect units this machine spawned (HazesAlive)

		string JointId(const string &in strain, int uses, bool main = false)
		{
			return (main ? JOINT_MH_PREFIX : JOINT_PREFIX) + strain + "_" + uses;
		}

		// hwp_joint_<strain>_<n> or hwp_joint_mh_<strain>_<n> -> strain, n and the hand; false
		// for anything else
		bool ParseJointId(const string &in id, string &out strain, int &out uses, bool &out main)
		{
			main = false;
			string prefix = JOINT_PREFIX;
			if (id.findFirst(JOINT_MH_PREFIX) == 0)
			{
				main = true;
				prefix = JOINT_MH_PREFIX;
			}
			else if (id.findFirst(JOINT_PREFIX) != 0)
				return false;
			int us = id.findLast("_");
			if (us <= int(prefix.length()))
				return false;
			strain = id.substr(prefix.length(), us - prefix.length());
			uses = int(parseInt(id.substr(us + 1)));
			return uses >= 1 && uses <= JOINT_USES && GetSeed(strain) !is null;
		}

		bool ParseJointId(const string &in id, string &out strain, int &out uses)
		{
			bool main;
			return ParseJointId(id, strain, uses, main);
		}

		bool ParseJoint(Equipment::Equipment@ eq, string &out strain, int &out uses, bool &out main)
		{
			main = false;
			auto item = cast<Equipment::Item>(eq);
			if (item is null || item.baseItem is null)
				return false;
			return ParseJointId(item.baseItem.m_id, strain, uses, main);
		}

		bool ParseJoint(Equipment::Equipment@ eq, string &out strain, int &out uses)
		{
			bool main;
			return ParseJoint(eq, strain, uses, main);
		}

		bool IsJoint(Equipment::Equipment@ eq)
		{
			string strain;
			int uses;
			return ParseJoint(eq, strain, uses);
		}

		Equipment::Item@ MakeJointById(const string &in id)
		{
			auto base = Equipment::BaseItem::Get(id);
			if (base is null)
			{
				HWP::LogError("farming", "no joint item " + id + " (tweak/hwp/equipment_joints.sval)");
				return null;
			}
			// as Generator.GenerateItem(BaseItem) (EquipmentGenerator.as:331) without its
			// VerifyItem: the joints' never-set conditional keeps them out of random drops
			Equipment::Generator gen;
			gen.m_ilvl = 1;
			Equipment::Item item;
			item.quality = Item::Quality::Common;
			@item.baseItem = base;
			gen.GenerateItemMods(item, 1, null);
			item.Finalize(randf(), 1, 0, null, null);
			return item;
		}

		EquippedItemsSlots SlotOf(bool main) { return main ? EquippedItemsSlots::MainHand : EquippedItemsSlots::OffHand; }
		string HandName(EquippedItemsSlots slot) { return slot == EquippedItemsSlots::MainHand ? "main" : "off"; }

		Equipment::Equipment@ HandItem(PlayerRecord@ rec, EquippedItemsSlots slot)
		{
			if (rec is null || rec.equipped is null)
				return null;
			return rec.equipped.m_items[int(slot)];
		}

		Equipment::Equipment@ OffHand(PlayerRecord@ rec) { return HandItem(rec, EquippedItemsSlots::OffHand); }
		Equipment::Equipment@ MainHand(PlayerRecord@ rec) { return HandItem(rec, EquippedItemsSlots::MainHand); }

		// the hand holding a joint, the off hand first; -1 for none
		int JointHand(PlayerRecord@ rec)
		{
			if (IsJoint(OffHand(rec)))
				return int(EquippedItemsSlots::OffHand);
			if (IsJoint(MainHand(rec)))
				return int(EquippedItemsSlots::MainHand);
			return -1;
		}

		void RefreshGear(PlayerRecord@ rec)
		{
			rec.RefreshStats();
			auto plr = cast<PlayerBase>(rec.actor);
			if (plr !is null)
				plr.RefreshModifiers();
		}

		// ---- the main-hand twin ---------------------------------------------------

		// the item's base swapped between the off-hand joint and its main-hand twin (the
		// same stage); true when it changed
		bool SwapJoint(Equipment::Equipment@ item, bool toMain)
		{
			auto it = cast<Equipment::Item>(item);
			string strain;
			int uses;
			bool main;
			if (it is null || !ParseJoint(it, strain, uses, main) || main == toMain)
				return false;
			auto twin = Equipment::BaseItem::Get(JointId(strain, uses, toMain));
			if (twin is null)
				return false;
			@it.baseItem = twin;
			return true;
		}

		// HWP::Bag::OnEquip: a joint clicked in the bag while the off hand already holds one
		// goes to the main hand (as its twin), unless a two-handed weapon is there
		void JointEquip(PlayerRecord@ rec, Equipment::Equipment@ item)
		{
			if (rec is null || rec.equipped is null || !IsJoint(item) || !IsJoint(OffHand(rec)))
				return;
			auto mh = MainHand(rec);
			if (mh !is null && mh.GetSlot() == Equipment::Slot::TwoHanded)
				return;
			if (SwapJoint(item, true))
				HWP::Log("farming", "joint to the main hand: " + cast<Equipment::Item>(item).baseItem.m_id);
		}

		// main-hand twins in the local bag back to off-hand joints, a few times a second
		int g_twinCheck = 0;

		void UpdateTwins(int ms)
		{
			g_twinCheck -= ms;
			if (g_twinCheck > 0)
				return;
			g_twinCheck = 250;
			auto rec = GetLocalPlayerRecord();
			if (rec is null || rec.equipInventory is null)
				return;
			for (uint i = 0; i < rec.equipInventory.m_items.length(); i++)
			{
				if (SwapJoint(rec.equipInventory.m_items[i], false))
				{
					rec.equipInventory.m_isDirty = true;
					HWP::Log("farming", "joint back in the bag as " + cast<Equipment::Item>(rec.equipInventory.m_items[i]).baseItem.m_id);
				}
			}
		}

		// hwp joint wield main|off: the newest bag joint into that hand (the main hand through
		// its twin); what was there goes to the bag
		bool WieldJoint(bool main)
		{
			auto rec = GetLocalPlayerRecord();
			if (rec is null || rec.equipInventory is null || rec.equipped is null)
				return false;
			Equipment::Item@ pick = null;
			for (int i = int(rec.equipInventory.m_items.length()) - 1; i >= 0 && pick is null; i--)
			{
				if (IsJoint(rec.equipInventory.m_items[i]))
					@pick = cast<Equipment::Item>(rec.equipInventory.m_items[i]);
			}
			if (pick is null)
			{
				HWP::Commands::Reply(Resources::GetString(".hwp.farming.joint.no_bag_joint"));
				return false;
			}
			SwapJoint(pick, main);
			if (!rec.equipped.MayEquip(pick) || !rec.equipInventory.Remove(pick))
			{
				SwapJoint(pick, false);
				HWP::Commands::Reply("cannot equip " + pick.baseItem.m_id);
				return false;
			}
			auto was = rec.equipped.Equip(pick, SlotOf(main));
			if (was is pick)
			{
				SwapJoint(pick, false);
				rec.equipInventory.Add(pick);
				HWP::Commands::Reply("cannot equip " + pick.baseItem.m_id);
				return false;
			}
			if (was !is null)
			{
				auto plr = cast<PlayerBase>(rec.actor);
				if (rec.equipInventory.CanAdd())
					rec.equipInventory.Add(was);
				else if (plr !is null)
					Item::DropItem(was, plr.m_unit.GetPosition(), 1, true, rec);
			}
			RefreshGear(rec);
			string text = Resources::GetString(".hwp.farming.joint.wielded", { { "name", pick.GetName() }, { "hand", HandName(SlotOf(main)) } });
			Say(text);
			HWP::Commands::Reply(text);
			HWP::Log("farming", "wielding " + pick.baseItem.m_id + " in the " + HandName(SlotOf(main)) + " hand");
			return true;
		}

		// ---- rolling (the materials tab) ----------------------------------------

		bool RollJoint(const string &in strain)
		{
			auto rec = GetLocalPlayerRecord();
			auto seed = GetSeed(strain);
			if (rec is null || seed is null || !seed.herb)
				return false;
			if (!g_enabled)
			{
				Say(Resources::GetString(".hwp.farming.off"));
				return false;
			}
			if (HWP::Market::Count(rec, strain) <= 0)
			{
				Say(Resources::GetString(".hwp.farming.no_herb", { { "name", seed.Name() } }));
				return false;
			}
			if (!rec.equipInventory.CanAdd())
			{
				Say(Resources::GetString(".hwp.farming.joint.bag_full"));
				return false;
			}
			auto joint = MakeJointById(JointId(strain, JOINT_USES));
			if (joint is null)
				return false;
			HWP::Market::Take(rec, strain, 1);
			rec.equipInventory.Add(joint);
			g_rolled++;
			string text = Resources::GetString(".hwp.farming.joint.rolled", { { "name", joint.GetName() } });
			Say(text);
			HWP::Commands::Reply(text);
			HWP::Log("farming", "rolled a " + strain + " joint (" + HWP::Market::Count(rec, strain) + " left)");
			return true;
		}

		// ---- the red tip (every machine) ----------------------------------------

		class LitJoint
		{
			PlayerBase@ m_player;
			Equipment::Equipment@ m_item;
			CustomUnitModel@ m_was;
			int m_ms;
		}
		array<LitJoint@> g_lit;
		dictionary g_litModels;

		CustomUnitModel@ LitModel(int uses, bool main)
		{
			string path = (main ? LIT_MODEL_MH : LIT_MODEL).replace("%n%", "" + uses);
			CustomUnitModel@ model;
			if (g_litModels.get(path, @model))
				return model;
			auto res = Resources::GetModel(path);
			if (res is null)
			{
				HWP::Log("farming", "lit joint model missing: " + path);
				return null;
			}
			@model = CustomUnitModel(res, g_plrMat);
			g_litModels.set(path, @model);
			return model;
		}

		void Unlight(LitJoint@ lit)
		{
			@lit.m_item.m_modelTmp = lit.m_was;
			if (lit.m_player !is null && lit.m_player.m_unit.IsValid())
				lit.m_player.RefreshScene();
		}

		void LightUp(PlayerBase@ player, bool main)
		{
			if (player is null)
				return;
			auto item = player.GetEquipment(SlotOf(main));
			string strain;
			int uses;
			bool isMain;
			if (!ParseJoint(item, strain, uses, isMain))
				return;
			auto model = LitModel(uses, isMain);
			if (model is null)
				return;
			for (uint i = 0; i < g_lit.length(); i++)
			{
				if (g_lit[i].m_player is player && g_lit[i].m_item is item)
				{
					g_lit[i].m_ms = LIT_MS;
					return;
				}
			}
			LitJoint lit;
			@lit.m_player = player;
			@lit.m_item = item;
			@lit.m_was = item.m_modelTmp;
			lit.m_ms = LIT_MS;
			g_lit.insertLast(lit);
			@item.m_modelTmp = model;
			player.RefreshScene();
		}

		// ---- the haze (every machine) -------------------------------------------

		// In town only inside a building: the vanilla interiors are edged with
		// env_mask_ceiling_inside_* tiles, so there are some on every side of you.
		bool Indoors(vec2 pos)
		{
			bool l = false, r = false, u = false, d = false;
			auto units = g_scene.FetchAllUnits(~0, pos, 220);
			for (uint i = 0; i < units.length(); i++)
			{
				if (!units[i].IsValid() || units[i].GetDebugName().findFirst("env_mask_ceiling_inside") < 0)
					continue;
				vec2 at = xy(units[i].GetPosition());
				if (dist(pos, at) > 220)
					continue;
				if (at.x < pos.x) l = true; else r = true;
				if (at.y < pos.y) u = true; else d = true;
			}
			return l && r && u && d;
		}

		// A run floor or a town building holds the smoke: one bank on the smoker. Outdoors in
		// town nothing does, so a puff hotboxes the square: a bank on the smoker and
		// HOTBOX_BANKS - 1 more around them, HOTBOX_RADIUS out.
		void SpawnHaze(PlayerBase@ player)
		{
			if (player is null || !player.m_unit.IsValid())
				return;
			vec2 pos = xy(player.m_unit.GetPosition());
			bool inside = !g_inTown || Indoors(pos);
			int banks = inside ? 1 : HOTBOX_BANKS;
			for (int i = 0; i < banks; i++)
			{
				vec2 at = pos;
				if (i > 0)
				{
					float a = float(i - 1) * 6.2832f / float(banks - 1) + randf() * 0.8f;
					at = vec2(pos.x + cos(a) * HOTBOX_RADIUS, pos.y + sin(a) * HOTBOX_RADIUS);
				}
				UnitPtr fx = PlayEffect(HAZE_FX, at);
				if (fx.IsValid())
					g_hazeUnits.insertLast(fx);
				g_hazes++;
			}
			HWP::Log("farming", "haze: " + banks + " bank(s) at " + int(pos.x) + "," + int(pos.y)
				+ (inside ? " (indoors)" : " (town outdoors, radius " + int(HOTBOX_RADIUS) + ")"));
		}

		// haze effect units of this level still alive (an effect unit goes when it has played out)
		int HazesAlive()
		{
			for (int i = int(g_hazeUnits.length()) - 1; i >= 0; i--)
				if (!g_hazeUnits[i].IsValid() || g_hazeUnits[i].IsDestroyed())
					g_hazeUnits.removeAt(i);
			return int(g_hazeUnits.length());
		}

		// ---- puffing --------------------------------------------------------------

		// the smoker's own machine: the joints to burn down once their tips cool, one per
		// hand. Globals reset with every level, so a pending burn is also kept in the
		// player's save bag (KEY_BURN / KEY_BURN_MH, the puffed joint's id) and Start finishes
		// it after a level change.
		const string KEY_BURN = "farm.joint_burn";       // the off hand's
		const string KEY_BURN_MH = "farm.joint_burn_mh"; // the main hand's

		class Burn
		{
			PlayerRecord@ m_rec;
			Equipment::Equipment@ m_item;
			EquippedItemsSlots m_slot;
			int m_ms;
		}
		array<Burn@> g_burns;

		string BurnKey(EquippedItemsSlots slot) { return slot == EquippedItemsSlots::MainHand ? KEY_BURN_MH : KEY_BURN; }

		Burn@ PendingBurn(EquippedItemsSlots slot)
		{
			for (uint i = 0; i < g_burns.length(); i++)
				if (g_burns[i].m_slot == slot)
					return g_burns[i];
			return null;
		}

		void Puffed(PlayerBase@ player, bool main)
		{
			// farm.enabled off: a held joint stays as it is (no buff, no burn, no haze)
			if (!g_enabled)
				return;
			LightUp(player, main);
			SpawnHaze(player);
			if (player is null || player.m_record is null || !player.m_record.local)
				return;
			auto slot = SlotOf(main);
			// a puff before the last one burned (a short cooldown): that stage burns first
			auto pending = PendingBurn(slot);
			if (pending !is null)
				BurnDown(pending);
			auto rec = player.m_record;
			auto item = HandItem(rec, slot);
			string strain;
			int uses;
			bool isMain;
			if (!ParseJoint(item, strain, uses, isMain))
				return;
			g_puffs++;
			ApplyHerb(rec, strain, main ? 1 : 0);
			Burn burn;
			@burn.m_rec = rec;
			@burn.m_item = item;
			burn.m_slot = slot;
			burn.m_ms = LIT_MS;
			g_burns.insertLast(burn);
			HWP::SaveData::Player(rec).SetString(BurnKey(slot), JointId(strain, uses, isMain));
			HWP::Log("farming", "puffed a " + strain + " joint (" + uses + " -> " + (uses - 1) + " puffs) in the "
				+ HandName(slot) + " hand");
		}

		void BurnDown(Burn@ burn)
		{
			int at = g_burns.findByRef(burn);
			if (at >= 0)
				g_burns.removeAt(at);
			auto rec = burn.m_rec;
			if (rec is null)
				return;
			HWP::SaveData::Player(rec).Remove(BurnKey(burn.m_slot));
			// taken, swapped or dropped meanwhile: it is someone else's now
			if (HandItem(rec, burn.m_slot) !is burn.m_item)
				return;
			BurnStage(rec, burn.m_slot);
		}

		// a level change before a tip cooled: the joint still in that hand burns its stage now
		void BurnPending()
		{
			auto rec = GetLocalPlayerRecord();
			if (rec is null)
				return;
			auto bag = HWP::SaveData::Player(rec);
			array<EquippedItemsSlots> slots = { EquippedItemsSlots::OffHand, EquippedItemsSlots::MainHand };
			for (uint i = 0; i < slots.length(); i++)
			{
				string id = bag.GetString(BurnKey(slots[i]));
				if (id == "")
					continue;
				bag.Remove(BurnKey(slots[i]));
				string strain;
				int uses;
				bool main;
				if (ParseJoint(HandItem(rec, slots[i]), strain, uses, main) && JointId(strain, uses, main) == id)
					BurnStage(rec, slots[i]);
			}
		}

		void BurnStage(PlayerRecord@ rec, EquippedItemsSlots slot)
		{
			string strain;
			int uses;
			bool main;
			if (!ParseJoint(HandItem(rec, slot), strain, uses, main))
				return;
			if (uses <= 1)
			{
				rec.equipped.Unequip(slot);
				RefreshGear(rec);
				Say(Resources::GetString(".hwp.farming.joint.done"));
				HWP::Log("farming", "the " + strain + " joint is smoked down (" + HandName(slot) + " hand)");
				return;
			}
			auto next = MakeJointById(JointId(strain, uses - 1, main));
			if (next is null)
				return;
			rec.equipped.Equip(next, slot);
			RefreshGear(rec);
		}

		void UpdateJoints(int ms)
		{
			for (int i = int(g_lit.length()) - 1; i >= 0; i--)
			{
				auto lit = g_lit[i];
				lit.m_ms -= ms;
				if (lit.m_ms > 0 && lit.m_player.m_unit.IsValid())
					continue;
				Unlight(lit);
				g_lit.removeAt(i);
			}
			for (int i = int(g_burns.length()) - 1; i >= 0; i--)
			{
				g_burns[i].m_ms -= ms;
				if (g_burns[i].m_ms <= 0)
					BurnDown(g_burns[i]);
			}
			UpdateTwins(ms);
		}

		void ClearJoints()
		{
			for (uint i = 0; i < g_lit.length(); i++)
				Unlight(g_lit[i]);
			g_lit.removeRange(0, g_lit.length());
			while (g_burns.length() > 0)
				BurnDown(g_burns[0]); // takes itself off the list
			BurnPending();
			g_hazeUnits.removeRange(0, g_hazeUnits.length());
			// a level start: the takes pending on the last level are gone with its scene clock
			g_handHolders.removeRange(0, g_handHolders.length());
			g_handTakers.removeRange(0, g_handTakers.length());
			g_handTimes.removeRange(0, g_handTimes.length());
		}

		// ---- passing it on --------------------------------------------------------

		PlayerRecord@ g_offerFrom; // the holder whose joint the hint was shown for

		bool FreeOffHand(PlayerRecord@ rec)
		{
			if (rec is null || rec.equipped is null || rec.IsDead())
				return false;
			auto main = rec.equipped.m_items[int(EquippedItemsSlots::MainHand)];
			if (main !is null && main.GetSlot() == Equipment::Slot::TwoHanded)
				return false;
			return OffHand(rec) is null;
		}

		// the nearest other player holding a joint (either hand) within reach of mine, or null
		PlayerRecord@ JointHolderNear(PlayerRecord@ me)
		{
			auto plr = cast<PlayerBase>(me.actor);
			if (plr is null || !plr.m_unit.IsValid())
				return null;
			vec2 at = xy(plr.m_unit.GetPosition());
			PlayerRecord@ best = null;
			float bestD = TAKE_RANGE;
			for (uint i = 0; i < g_players.length(); i++)
			{
				auto other = g_players[i];
				if (other is null || other is me || other.peer == 255 || other.IsDead() || JointHand(other) < 0)
					continue;
				auto op = cast<PlayerBase>(other.actor);
				if (op is null || !op.m_unit.IsValid())
					continue;
				float d = dist(at, xy(op.m_unit.GetPosition()));
				if (d <= bestD)
				{
					bestD = d;
					@best = other;
				}
			}
			return best;
		}

		void PollTake(GameInput& gameInput)
		{
			auto me = GetLocalPlayerRecord();
			auto holder = FreeOffHand(me) ? JointHolderNear(me) : null;
			if (holder is null)
			{
				@g_offerFrom = null;
				return;
			}
			if (holder !is g_offerFrom)
			{
				@g_offerFrom = holder;
				auto op = cast<PlayerBase>(holder.actor);
				AddFloatingText(FloatingTextType::Pickup, Resources::GetString(".hwp.farming.joint.take_hint", {
					{ "key", FormatKeyName(GetActionBinding("Use")) }, { "name", holder.GetName() } }), op.m_unit.GetPosition());
			}
			if (!gameInput.Use.Pressed)
				return;
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("holder", holder.peer);
			b.PopDictionary();
			HWP::Net::Request(JOINT_TAKE, b.Build());
			HWP::Log("farming", "asked " + holder.GetName() + " for the joint");
		}

		// host: the hand-overs it asked a holder for (holder peer -> taker peer, and when), so a
		// JOINT_GIVE is relayed only for a take it checked, never made up by a peer. The first
		// take wins: a second one while the first is pending is refused, since the holder lets
		// go of the joint before the host sees its give. A take that got no give for
		// HAND_EXPIRE ms (the holder put it away, or left) no longer blocks the next. A level
		// start clears them all (ClearJoints).
		array<int> g_handHolders;
		array<int> g_handTakers;
		array<int> g_handTimes;
		const int HAND_EXPIRE = 5000;

		// host: within reach (a little slack for the lag between the two machines)?
		bool CanTake(PlayerRecord@ taker, PlayerRecord@ holder)
		{
			if (taker is null || holder is null || JointHand(holder) < 0)
				return false;
			auto tp = cast<PlayerBase>(taker.actor);
			auto hp = cast<PlayerBase>(holder.actor);
			return tp !is null && hp !is null && tp.m_unit.IsValid() && hp.m_unit.IsValid()
				&& dist(xy(tp.m_unit.GetPosition()), xy(hp.m_unit.GetPosition())) <= TAKE_RANGE * 2.0f;
		}

		// host
		void OnJointTake(uint8 peer, SValue@ data)
		{
			int holder = HWP::SV::Int(data, "holder", -1);
			if (holder < 0 || holder > 255 || holder == int(peer))
				return;
			if (!CanTake(GetPlayerRecordByPeer(peer), GetPlayerRecordByPeer(uint8(holder))))
			{
				HWP::Log("farming", "refused peer " + peer + "'s take from peer " + holder + " (no joint or out of reach)");
				return;
			}
			int now = g_scene.GetTime();
			int at = g_handHolders.find(holder);
			if (at < 0)
			{
				g_handHolders.insertLast(holder);
				g_handTakers.insertLast(int(peer));
				g_handTimes.insertLast(now);
			}
			else
			{
				int age = now - g_handTimes[at];
				if (g_handTakers[at] != int(peer) && age < HAND_EXPIRE)
				{
					HWP::Log("farming", "refused peer " + peer + "'s take from peer " + holder + " (peer "
						+ g_handTakers[at] + " asked first)");
					return;
				}
				g_handTakers[at] = int(peer);
				g_handTimes[at] = now;
			}
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("taker", peer);
			b.PopDictionary();
			HWP::Net::Send(uint8(holder), JOINT_HAND, b.Build());
		}

		// the holder: hand it over if it is still in a hand (the off hand first); the taker
		// gets it as an off-hand joint
		void OnJointHand(SValue@ data)
		{
			int taker = HWP::SV::Int(data, "taker", -1);
			auto rec = GetLocalPlayerRecord();
			int hand = JointHand(rec);
			if (taker < 0 || hand < 0)
				return;
			auto slot = SlotOf(hand == int(EquippedItemsSlots::MainHand));
			auto pending = PendingBurn(slot);
			if (pending !is null)
			{
				BurnDown(pending); // the stage burns first; what is left goes over
				hand = JointHand(rec);
				if (hand < 0)
					return;
				slot = SlotOf(hand == int(EquippedItemsSlots::MainHand));
			}
			string strain;
			int uses;
			bool main;
			if (!ParseJoint(HandItem(rec, slot), strain, uses, main))
				return;
			string id = JointId(strain, uses);
			rec.equipped.Unequip(slot);
			RefreshGear(rec);
			g_given++;
			auto taker_ = GetPlayerRecordByPeer(uint8(taker));
			Say(Resources::GetString(".hwp.farming.joint.taken_from", { { "name", taker_ is null ? "?" : taker_.GetName() } }));
			HWP::Log("farming", "handed the joint (" + id + ", " + HandName(slot) + " hand) to peer " + taker);
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("taker", taker);
			b.PushString("id", id);
			b.PopDictionary();
			HWP::Net::Request(JOINT_GIVE, b.Build());
		}

		// host
		void OnJointGive(uint8 peer, SValue@ data)
		{
			int taker = HWP::SV::Int(data, "taker", -1);
			string id = HWP::SV::Str(data, "id");
			string strain;
			int uses;
			int at = g_handHolders.find(int(peer));
			if (at < 0 || !ParseJointId(id, strain, uses) || uses < 1 || uses > JOINT_USES)
			{
				HWP::Log("farming", "refused peer " + peer + "'s joint for peer " + taker + " (no take asked for it)");
				return;
			}
			// a take was checked for this holder, but for someone else (its first take expired
			// and another replaced it): the holder has already let go, so it gets the joint back
			int to = g_handTakers[at] == taker ? taker : int(peer);
			if (to != taker)
				HWP::Log("farming", "peer " + peer + "'s joint for peer " + taker + " goes back to it (peer "
					+ g_handTakers[at] + "'s take is the one pending)");
			g_handHolders.removeAt(at);
			g_handTakers.removeAt(at);
			g_handTimes.removeAt(at);
			SValueBuilder b;
			b.PushDictionary();
			b.PushString("id", id);
			b.PopDictionary();
			HWP::Net::Send(uint8(to), JOINT_GET, b.Build());
		}

		// the taker: into the off hand, or the bag if it was filled meanwhile
		void OnJointGet(SValue@ data)
		{
			string id = HWP::SV::Str(data, "id");
			string strain;
			int uses;
			auto rec = GetLocalPlayerRecord();
			if (rec is null || !ParseJointId(id, strain, uses))
				return;
			auto joint = MakeJointById(JointId(strain, uses)); // the off-hand form, whichever hand it came from
			if (joint is null)
				return;
			g_taken++;
			if (FreeOffHand(rec) && rec.equipped.Equip(joint, EquippedItemsSlots::OffHand) !is joint)
			{
				RefreshGear(rec);
				HWP::Log("farming", "took a joint (" + id + ") into the off hand");
			}
			else if (rec.equipInventory.CanAdd())
			{
				rec.equipInventory.Add(joint);
				HWP::Log("farming", "took a joint (" + id + ") into the bag");
			}
			else
			{
				auto plr = cast<PlayerBase>(rec.actor);
				if (plr !is null)
					Item::DropItem(joint, plr.m_unit.GetPosition(), 1, true, rec);
				HWP::Log("farming", "took a joint (" + id + "); hands and bag full, at my feet");
			}
			Say(Resources::GetString(".hwp.farming.joint.took", { { "name", joint.GetName() } }));
		}

		string HandStatus(PlayerRecord@ rec, EquippedItemsSlots slot)
		{
			string strain;
			int uses;
			if (!ParseJoint(HandItem(rec, slot), strain, uses))
				return "none";
			return strain + " " + uses + "/" + JOINT_USES;
		}

		// "joint: held <off hand>, main <main hand>, rolled N, puffs N, hazes N (alive M), lit N,
		// taken N, given N; herb: ..." (GameLab reads it: gamelab/bots/plan_farming.py joint_status)
		string JointStatus()
		{
			auto rec = GetLocalPlayerRecord();
			return "joint: held " + HandStatus(rec, EquippedItemsSlots::OffHand) + ", main " + HandStatus(rec, EquippedItemsSlots::MainHand)
				+ ", rolled " + g_rolled + ", puffs " + g_puffs + ", hazes " + g_hazes + " (alive " + HazesAlive() + "), lit " + g_lit.length()
				+ ", taken " + g_taken + ", given " + g_given + "; " + HerbStatus();
		}
	}
}

// the cast-point action of hwp_joint_puff / hwp_joint_puff_mh (attacks_joint.sval): "hand"
// names the joint it puffs, "off" (the default) or "main"
class HWPJointPuff : IAction
{
	bool m_main;

	HWPJointPuff(UnitPtr unit, SValue& params)
	{
		m_main = GetParamString(unit, params, "hand", false, "off") == "main";
	}

	void CancelAction() {}
	void SetWeaponInformation(uint weapon) {}
	bool NeedNetParams() { return false; }
	void Update(int dt, int cooldown) {}

	bool DoAction(SValueBuilder@ builder, Actor@ owner, Actor@ target, vec2 pos, vec2 dir, float intensity)
	{
		HWP::Farming::Puffed(cast<PlayerBase>(owner), m_main);
		return true;
	}

	bool NetDoAction(SValue@ param, Actor@ owner, vec2 pos, vec2 dir)
	{
		HWP::Farming::Puffed(cast<PlayerBase>(owner), m_main);
		return true;
	}
}

// "Roll J?" -> "Huzzah!" (HWPHarvestMaterial.Click)
class HWPRollJointHost : IWidgetHoster
{
	string m_strain;
	HWPRollJointHost(const string &in strain) { m_strain = strain; }

	void OnFunc(Widget@ sender, const string &in name) override
	{
		if (name == "hwproll yes")
			HWP::Farming::RollJoint(m_strain);
	}
}
