// Pets without a Watcher of their own (vanilla pets: the Pets package is not
// there, or its pet classes are not in play) get one here, keyed by the pet's
// unit. While it parks the pet, the pet's own Update must not run, and a
// module cannot skip it, so the owner's own (not husk) pet loses its m_owner
// between frames: MiniPetWalking/MiniPetFlying.Update return at once without
// one, and nothing else reads it then (PlayerHandler's SetPetTarget only
// reaches husk pets). Each tick gives every owner back before anything else
// and takes them again only after every Watcher has stepped, so a tick that
// fails (HWP::Guard then turns the module off) leaves no pet without one. A husk pet keeps its owner and
// has its target cleared each tick: its own Update only walks to a target.
namespace HWP
{
	namespace PetWait
	{
		void OnSettingChanged(const string &in key)
		{
			if (key.findFirst("petwait.") == 0)
				RefreshSettings();
		}

		class Driven
		{
			MiniPet@ m_pet;
			PlayerBase@ m_owner;  // set while m_pet.m_owner is held off
			Watcher m_wait;
			int m_leash;

			void Release()
			{
				if (m_owner is null)
					return;
				@m_pet.m_owner = m_owner;
				@m_owner = null;
			}
		}

		array<Driven@> g_driven;

		Driven@ DrivenFor(MiniPet@ pet)
		{
			for (uint i = 0; i < g_driven.length(); i++)
				if (g_driven[i].m_pet is pet)
					return g_driven[i];
			Driven d;
			@d.m_pet = pet;
			d.m_wait.m_flying = cast<MiniPetFlying>(pet) !is null;
			d.m_leash = pet.m_leashRange;
			return d;
		}

		void ReleaseAll()
		{
			for (uint i = 0; i < g_driven.length(); i++)
				g_driven[i].Release();
		}

		void Tick(int dt)
		{
			ReleaseAll();
			array<Driven@> now;
			array<Driven@> hold;
			for (uint i = 0; i < g_players.length(); i++)
			{
				auto rec = g_players[i];
				auto pb = rec is null ? null : cast<PlayerBase>(rec.actor);
				if (pb is null || pb.m_pet is null || !pb.m_pet.m_unit.IsValid() || cast<Owned>(pb.m_pet) !is null)
					continue;
				Driven@ d = DrivenFor(pb.m_pet);
				now.insertLast(d);
				if (!d.m_wait.Step(dt, d.m_pet, pb))
				{
					d.m_pet.m_leashRange = d.m_leash;
					continue;
				}
				d.m_pet.ClearTarget();
				auto flying = cast<MiniPetFlying>(d.m_pet);
				if (flying !is null)
				{
					flying.m_dir = d.m_wait.m_angle;
					flying.m_currentSpeed = 0;
				}
				if (!pb.IsHusk())
					hold.insertLast(d);
			}
			g_driven = now;
			for (uint i = 0; i < hold.length(); i++)
			{
				hold[i].m_pet.m_leashRange = 1000000; // given back before its owner: no leash pull
				@hold[i].m_owner = hold[i].m_pet.m_owner;
				@hold[i].m_pet.m_owner = null;
			}
		}
	}
}

namespace Modules
{
	class HWPPetRoomsModule : Module, HWP::ModuleStart
	{
		HWPPetRoomsModule()
		{
			super("hwp-petrooms");
			HWP::PetWait::g_driven.resize(0);
			HWP::Commands::OnSettingChanged(HWP::Commands::SettingListener(HWP::PetWait::OnSettingChanged));
		}

		void Start(StartMode sMode)
		{
			HWP::Settings::Sync("petwait.");
			HWP::PetWait::RefreshSettings();
			HWP::PetWait::g_driven.resize(0);
		}

		// HWP::Guard (tools/guard_modules.py): a script error here turns this off, not the game
		HWP::Guard m_guardUpdateFrame;
		void UpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused) override
		{
			if (m_guardUpdateFrame.Skip("petrooms", "HWPPetRoomsModule.UpdateFrame"))
				return;
			if (m_guardUpdateFrame.Raw())
			{
				GuardedUpdateFrame(ms, gameInput, menuInput, paused);
				m_guardUpdateFrame.Ok();
				return;
			}
			try { GuardedUpdateFrame(ms, gameInput, menuInput, paused); m_guardUpdateFrame.Ok(); }
			catch { m_guardUpdateFrame.Failed(); }
		}

		void GuardedUpdateFrame(int ms, GameInput& gameInput, MenuInput& menuInput, bool paused)
		{
			if (paused)
				return;
			HWP::PetWait::Tick(ms);
		}
	}
}
