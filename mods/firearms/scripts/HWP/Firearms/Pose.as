// Gun poses: how the held guns point between, during and after shots (the user, 2026-10-22).
//
//   pistols (Glock, Hand Cannon, either hand)   rifle (rifle, Flamethrower, Full Auto)
//   idle (walking about)   both up              down
//   firing                 straight; the hand    straight, through the whole burst and
//                          that just shot kicks  between its shots
//                          up for 100 ms
//   reloading              both down             up
//   secondary              -                     45 degrees up (launcher, flamethrower);
//                                                straight for Full Auto
//   firing stops           1 s after the last shot, or at once on a dodge or any other skill
//
// The animation sets have no aimed-up or aimed-down poses (players/models/anim_sets.sval:
// the rifle is the 2h crossbow set, the pistols the wand set) and the scripts reach no
// bone, so a pose is the gun's own model turned about the hand: pre-rotated copies of each
// gun model (players/models/equipment/pose_<gun>_<pose>.model, from the job script
// make_pose_models.py through tools/make_gun_models.py's reader and writer: pistols up 90,
// kick 40, down -75 degrees; rifles down -40, up 70, high 45) swapped into the item's
// Equipment::m_modelTmp, the slot PlayerVisuals::GetModel draws in place of the item's own
// model, the way the held guns do it (HeldModel.as). The arm itself still follows the
// animation (the shot's first frame pinned by Combat.as AimHold while firing).
//
// The local player's state is read every frame (UpdateCombat): the reloading stack or the
// Reload cast, an active gun skill (Combat.as GUNS), the rifle's secondary skill, any other
// active skill (an ability or a dodge). A hand's kick comes from the round that left it
// (Elemental.as HWPFirearmsGunShot.ProduceProjectile, PoseShot). Each change of pose is one
// "[HWP:firearms] pose: ..." line; `hwp firearms pose` reports the state. A held gun
// (HeldModel.as g_heldGuns: Sniper Shot, the launchers) owns m_modelTmp while it lasts.
//
// Other players see the state poses too: a state change goes to the host as the HWP::Net
// request "firearms.pose" and comes back to everyone as the event, applied to that peer's
// player (a husk) by the same model swap. The 100 ms kicks stay local (AimHold's pin was
// never synced either; the peers see the game's own shot animation).
namespace HWP
{
	namespace Firearms
	{
		enum GunPose { PoseStraight = 0, PoseUp, PoseDown, PoseKick, PoseHigh }
		const array<string> POSE_NAMES = { "straight", "up", "down", "kick", "high" };
		const int POSE_IDLE_MS = 1000;
		const int POSE_KICK_MS = 100;
		const string POSE_EVENT = "firearms.pose";
		const array<uint> POSE_SECONDARY = { HashString("hwp_attack_rifle_gl"), HashString("hwp_attack_rifle_gl_epic"),
			HashString("hwp_attack_flamer") };

		// the pose-model family of the gun in a hand ("glock_oh", "rifle"); "" for no gun with poses
		string PoseGun(PlayerBase@ plr, bool off)
		{
			if (plr is null || plr.m_record is null)
				return "";
			string id = MagazineItemId(plr.m_record, off);
			if (id.findFirst("hwp_glock_") == 0)
				return off ? "glock_oh" : "glock_mh";
			if (id.findFirst("hwp_hcannon_") == 0)
				return off ? "hcannon_oh" : "hcannon_mh";
			if (off)
				return "";
			if (id.findFirst("hwp_flamerifle_") == 0)
				return "flamerifle";
			if (id.findFirst("hwp_autorifle_") == 0)
				return "autorifle";
			if (id.findFirst("hwp_rifle_") == 0)
				return "rifle";
			return "";
		}

		bool PoseIsRifle(const string &in gun)
		{
			return gun == "rifle" || gun == "flamerifle" || gun == "autorifle";
		}

		string PoseModelPath(const string &in gun, int pose)
		{
			if (gun == "" || pose == PoseStraight)
				return "";
			return "players/models/equipment/pose_" + gun + "_" + POSE_NAMES[pose] + ".model";
		}

		bool HeldGunOn(PlayerBase@ plr)
		{
			for (uint i = 0; i < g_heldGuns.length(); i++)
				if (g_heldGuns[i].m_player is plr)
					return true;
			return false;
		}

		// one hand of one player: the item posed and the model it had before any pose
		class PosedHand
		{
			Equipment::Equipment@ m_item;
			CustomUnitModel@ m_was;
			int m_pose = PoseStraight;
		}

		class PosedPlayer
		{
			PlayerBase@ m_plr;
			PosedHand m_main;
			PosedHand m_off;
			int m_wantMain = PoseStraight;
			int m_wantOff = PoseStraight;

			// put the wanted models on the items; true when the scene was rebuilt
			bool Apply()
			{
				if (m_plr is null || !m_plr.m_unit.IsValid() || m_plr.m_record is null || HeldGunOn(m_plr))
					return false;
				bool changed = false;
				changed = ApplyHand(m_main, m_plr.GetEquipment(EquippedItemsSlots::MainHand), PoseGun(m_plr, false), m_wantMain) || changed;
				changed = ApplyHand(m_off, m_plr.GetEquipment(EquippedItemsSlots::OffHand), PoseGun(m_plr, true), m_wantOff) || changed;
				if (changed)
					m_plr.RefreshScene();
				return changed;
			}

			bool ApplyHand(PosedHand@ hand, Equipment::Equipment@ item, const string &in gun, int pose)
			{
				bool changed = false;
				if (hand.m_item !is null && hand.m_item !is item)
				{
					// the gun left the hand: its own model back on it, wherever it is now
					if (hand.m_item.m_modelTmp !is hand.m_was)
					{
						@hand.m_item.m_modelTmp = hand.m_was;
						changed = true;
					}
					@hand.m_item = null;
					@hand.m_was = null;
					hand.m_pose = PoseStraight;
				}
				if (item is null || gun == "")
					return changed;
				if (hand.m_item is null)
				{
					@hand.m_item = item;
					@hand.m_was = item.m_modelTmp;
				}
				CustomUnitModel@ want = hand.m_was;
				string path = PoseModelPath(gun, pose);
				if (path != "")
				{
					auto model = HeldModel(path);
					if (model !is null)
						@want = model;
				}
				hand.m_pose = pose;
				if (item.m_modelTmp is want)
					return changed;
				@item.m_modelTmp = want;
				return true;
			}

			void Clear()
			{
				m_wantMain = PoseStraight;
				m_wantOff = PoseStraight;
				bool changed = false;
				if (m_main.m_item !is null && m_main.m_item.m_modelTmp !is m_main.m_was)
				{
					@m_main.m_item.m_modelTmp = m_main.m_was;
					changed = true;
				}
				if (m_off.m_item !is null && m_off.m_item.m_modelTmp !is m_off.m_was)
				{
					@m_off.m_item.m_modelTmp = m_off.m_was;
					changed = true;
				}
				@m_main.m_item = null;
				@m_off.m_item = null;
				if (changed && m_plr !is null && m_plr.m_unit.IsValid())
					m_plr.RefreshScene();
			}
		}

		// the local player's state machine
		class PoseState
		{
			PosedPlayer m_posed;
			string m_state = "";
			int m_sinceShot = POSE_IDLE_MS;
			int m_kickMain = 0;
			int m_kickOff = 0;
			int m_changes = 0;
			int m_kicks = 0;
			string m_last = "";

			void Reset()
			{
				m_posed.Clear();
				@m_posed.m_plr = null;
				m_state = "";
				m_sinceShot = POSE_IDLE_MS;
				m_kickMain = 0;
				m_kickOff = 0;
			}

			// a round left this hand (local player): the pistol kicks up for POSE_KICK_MS
			void Shot(bool off)
			{
				if (off)
					m_kickOff = POSE_KICK_MS;
				else
					m_kickMain = POSE_KICK_MS;
				m_sinceShot = 0;
			}

			void Update(PlayerBase@ plr, int ms)
			{
				if (m_posed.m_plr !is plr)
				{
					m_posed.Clear();
					@m_posed.m_plr = plr;
					m_state = "";
				}
				string mainGun = PoseGun(plr, false);
				string offGun = PoseGun(plr, true);
				if (mainGun == "" && offGun == "")
				{
					if (m_state != "")
					{
						m_posed.Clear();
						m_state = "";
						HWP::Log("firearms", "pose: off (no gun with poses in hand)");
					}
					return;
				}

				bool reloading = ReloadCasting(plr);
				auto reload = ActorBuffStackDef::Get(RELOADING);
				if (reload !is null && plr.GetStacks(reload) > 0)
					reloading = true;
				bool shooting = false;
				bool secondary = false;
				bool other = false;
				for (uint i = 0; i < plr.m_skills.length(); i++)
				{
					auto skill = cast<Skills::PlayerSkill>(plr.m_skills[i]);
					auto active = cast<Skills::ActiveSkill>(plr.m_skills[i]);
					bool on = (skill !is null && skill.IsActive()) || (active !is null && active.IsActive());
					if (!on)
						continue;
					uint id = plr.m_skills[i].m_skillId;
					if (id == RELOAD_ID)
						continue;
					if (POSE_SECONDARY.find(id) >= 0)  // before GUNS: the launcher is in both
						secondary = true;
					else if (GUNS.find(id) >= 0)
						shooting = true;
					else
						other = true;
				}

				m_kickMain = max(0, m_kickMain - ms);
				m_kickOff = max(0, m_kickOff - ms);
				string state;
				if (reloading)
					state = "reloading";
				else if (secondary)
					state = "secondary";
				else if (shooting)
				{
					state = "firing";
					m_sinceShot = 0;
				}
				else if (other)
				{
					state = "idle";
					m_sinceShot = POSE_IDLE_MS;
				}
				else
				{
					m_sinceShot = min(POSE_IDLE_MS, m_sinceShot + ms);
					state = m_sinceShot < POSE_IDLE_MS ? "firing" : "idle";
				}
				if (state != "firing")
				{
					m_kickMain = 0;
					m_kickOff = 0;
				}

				int wantMain = HandPose(mainGun, state, m_kickMain > 0);
				int wantOff = HandPose(offGun, state, m_kickOff > 0);
				bool stateChanged = state != m_state;
				string why = state;
				if (stateChanged)
				{
					if (state == "idle" && other)
						why += " (another skill)";
					else if (state == "idle" && m_state == "firing")
						why += " (" + POSE_IDLE_MS + " ms without a shot)";
					m_state = state;
				}
				if (wantMain != m_posed.m_wantMain || wantOff != m_posed.m_wantOff || stateChanged)
				{
					bool kick = (wantMain == PoseKick && m_posed.m_wantMain != PoseKick)
						|| (wantOff == PoseKick && m_posed.m_wantOff != PoseKick);
					m_posed.m_wantMain = wantMain;
					m_posed.m_wantOff = wantOff;
					m_changes++;
					if (kick)
						m_kicks++;
					m_last = "main " + (mainGun == "" ? "-" : POSE_NAMES[wantMain]) + ", off "
						+ (offGun == "" ? "-" : POSE_NAMES[wantOff]) + " (" + why + ")";
					HWP::Log("firearms", "pose: " + m_last);
					if (stateChanged)
						SendPose(plr, HandPose(mainGun, state, false), HandPose(offGun, state, false));
				}
				m_posed.Apply();
			}

			int HandPose(const string &in gun, const string &in state, bool kick)
			{
				if (gun == "")
					return PoseStraight;
				bool rifle = PoseIsRifle(gun);
				if (state == "reloading")
					return rifle ? PoseUp : PoseDown;
				if (state == "secondary")
					return rifle ? PoseHigh : PoseStraight;
				if (state == "firing")
					return (!rifle && kick) ? PoseKick : PoseStraight;
				return rifle ? PoseDown : PoseUp;
			}
		}
		PoseState g_pose;

		// the other players' state poses, by peer
		array<PosedPlayer@> g_peerPoses;

		PosedPlayer@ PeerPosed(uint8 peer)
		{
			for (uint i = 0; i < g_players.length(); i++)
			{
				auto rec = g_players[i];
				if (rec is null || rec.peer != peer)
					continue;
				auto plr = cast<PlayerBase>(rec.actor);
				if (plr is null)
					return null;
				for (uint j = 0; j < g_peerPoses.length(); j++)
				{
					if (g_peerPoses[j].m_plr is plr)
						return g_peerPoses[j];
				}
				PosedPlayer@ p = PosedPlayer();
				@p.m_plr = plr;
				g_peerPoses.insertLast(p);
				return p;
			}
			return null;
		}

		void SendPose(PlayerBase@ plr, int mainPose, int offPose)
		{
			if (plr is null || plr.m_record is null)
				return;
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("peer", int(plr.m_record.peer));
			b.PushInteger("main", mainPose);
			b.PushInteger("off", offPose);
			b.PopDictionary();
			HWP::Net::Request(POSE_EVENT, b.Build());
		}

		// host: a player's pose state, passed on to everyone with the sending peer's number
		void OnPoseRequest(uint8 peer, SValue@ data)
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("peer", int(peer));
			b.PushInteger("main", HWP::SV::Int(data, "main", 0));
			b.PushInteger("off", HWP::SV::Int(data, "off", 0));
			b.PopDictionary();
			HWP::Net::Broadcast(POSE_EVENT, b.Build());
		}

		// everyone: another player's guns take the pose (the local player's own are already posed)
		void OnPoseEvent(SValue@ data)
		{
			int peer = HWP::SV::Int(data, "peer", -1);
			if (peer < 0 || peer > 255 || peer == Lobby::GetLocalPeer())
				return;
			auto posed = PeerPosed(uint8(peer));
			if (posed is null)
				return;
			posed.m_wantMain = clamp(HWP::SV::Int(data, "main", 0), 0, int(POSE_NAMES.length()) - 1);
			posed.m_wantOff = clamp(HWP::SV::Int(data, "off", 0), 0, int(POSE_NAMES.length()) - 1);
			HWP::Log("firearms", "pose: peer " + peer + " main " + POSE_NAMES[posed.m_wantMain] + ", off " + POSE_NAMES[posed.m_wantOff]);
			posed.Apply();
		}

		void PoseNetRegister()
		{
			HWP::Net::OnRequest(POSE_EVENT, HWP::Net::RequestHandler(OnPoseRequest));
			HWP::Net::OnEvent(POSE_EVENT, HWP::Net::EventHandler(OnPoseEvent));
		}

		// a round left a hand: the local player's pistol kicks
		void PoseShot(Actor@ shooter, bool off)
		{
			auto plr = cast<PlayerBase>(shooter);
			if (plr !is null && plr is cast<PlayerBase>(GetLocalPlayer()))
				g_pose.Shot(off);
		}

		// every frame: the local player's state, and the peers' poses kept on their items
		void UpdatePose(int ms)
		{
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			if (plr !is null && IsFirearms(GetLocalPlayerRecord()))
				g_pose.Update(plr, ms);
			else if (g_pose.m_state != "")
				g_pose.Reset();
			for (int i = int(g_peerPoses.length()) - 1; i >= 0; i--)
			{
				auto p = g_peerPoses[i];
				if (p.m_plr is null || !p.m_plr.m_unit.IsValid())
				{
					g_peerPoses.removeAt(i);
					continue;
				}
				p.Apply();
			}
		}

		void ResetPoses()
		{
			g_pose.Reset();
			for (uint i = 0; i < g_peerPoses.length(); i++)
				g_peerPoses[i].Clear();
			g_peerPoses.removeRange(0, g_peerPoses.length());
		}

		// "hwp firearms pose"
		string PoseStatus()
		{
			auto plr = cast<PlayerBase>(GetLocalPlayer());
			string guns = plr is null ? "-" : (PoseGun(plr, false) == "" ? "-" : PoseGun(plr, false)) + "/" + (PoseGun(plr, true) == "" ? "-" : PoseGun(plr, true));
			return "pose: state " + (g_pose.m_state == "" ? "off" : g_pose.m_state) + ", guns " + guns
				+ ", now " + (g_pose.m_last == "" ? "-" : g_pose.m_last) + ", changes " + g_pose.m_changes
				+ ", kicks " + g_pose.m_kicks + ", since shot " + g_pose.m_sinceShot + " ms"
				+ ", held gun " + ((plr !is null && HeldGunOn(plr)) ? "yes" : "no") + ", peers posed " + g_peerPoses.length();
		}
	}
}
