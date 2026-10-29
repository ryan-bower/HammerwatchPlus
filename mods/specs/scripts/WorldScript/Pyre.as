// HWP specs override of scripts/WorldScript/Pyre.as (the large pyre; the pristine copy is
// Pyre.as.orig). Two lines for the Devil Forgemaster, the same rules as the class-swapped
// brazier (HWPSpecsPyre, Forgemaster.as): CanUse lets a Forgemaster with Heresy use it with no
// curse, and Use removes Pyre Sacrifice's Heresy once (the user, 2026-10-25: "large pyres don't
// count towards removing heresy, they should"). A WorldScript is not a unit behaviour, so no
// class swap reaches it.
namespace WorldScript
{
	[WorldScript color="210 105 30" icon="system/icons.png;384;224;32;32"]
	class Pyre : IUsable
	{
		bool Enabled;
		vec3 Position;

		[Editable]
		array<CollisionArea@>@ Areas;
	
		[Editable]
		UnitFeed Unit;
		[Editable]
		string UseScene;
		
		[Editable]
		SoundEvent@ Sound;
	
		SoundInstance@ m_sndInstance;
		bool m_used = false;
	

		void Initialize()
		{
			for (uint i = 0; i < Areas.length(); i++)
			{
				Areas[i].AddOnEnter(this, "OnEnter");
				Areas[i].AddOnExit(this, "OnExit");
			}
			
			if (Sound !is null)
			{
				@m_sndInstance = Sound.PlayTracked(Position);
				m_sndInstance.SetLooped(true);
				m_sndInstance.SetPaused(false);
			}
		}

		Player@ GetPlayer(UnitPtr unit)
		{
			if (!unit.IsValid())
				return null;
			
			ref@ behavior = unit.GetScriptBehavior();
			
			if (behavior is null)
				return null;
		
			return cast<Player>(behavior);
		}

		bool IsInside(UnitPtr unit)
		{
			for (uint i = 0; i < Areas.length(); i++)
				if (Areas[i].IsInside(unit))
					return true;
			return false;
		}
		
		void OnEnter(UnitPtr unit, vec2 pos, vec2 normal)
		{
			Player@ plr = GetPlayer(unit);
			if (plr !is null)
				plr.AddUsable(this);
		}
		
		void OnExit(UnitPtr unit)
		{
			Player@ plr = GetPlayer(unit);
			if (plr !is null)
				plr.RemoveUsable(this);
		}

		UnitPtr GetUseUnit()
		{
			return WorldScript::GetWorldScript(g_scene, this).GetUnit();
		}

		bool CanUse(PlayerBase@ player)
		{
			if (!Enabled)
				return false;

			if (m_used && player.m_record.local)
				return false;

			if (cast<PlayerHusk>(player) !is null)
				return true;

			auto record = player.m_record;
			if (record.shadowCurses <= 0)
				return HWP::Specs::PyreHeresyAllows(player);   // HWP specs: a Forgemaster with Heresy needs no curse

			return true;
		}
		
		void Use(PlayerBase@ player)
		{
			bool wasUsed = m_used;   // HWP specs: Pyre Sacrifice's Heresy, once, on the user's own client
			int cursesBefore = player.m_record.shadowCurses;
			if (UseScene != "")
			{
				auto units = Unit.FetchAll();
				for (uint i = 0; i < units.length(); i++)
					units[i].SetUnitScene(UseScene, true);
			}

			if (m_sndInstance !is null)
			{
				m_sndInstance.Stop();
				@m_sndInstance = null;
			}

			auto record = player.m_record;
			
			
			int toRem = max(8, record.shadowCurses / 2.0f);
			toRem = min(toRem, record.shadowCurses);
			
			record.shadowCurses -= toRem;

			LootLog::PresentPickup(record, LootLog::g_lootStrShadowCurse, -toRem);
			AddFloatingText(FloatingTextType::Pickup, "-" + toRem, player.m_unit.GetPosition());

			if (toRem > 0)
				%STAT Add shadow-curse-removed toRem record

			if (!m_used)
				%STAT Add pyres-used 1 record

			m_used = true;
			if (!wasUsed)
				HWP::Specs::PyreHeresyUsed(player, "large", cursesBefore);
		}
		
		SValue@ Save()
		{
			SValueBuilder sval;
			sval.PushBoolean(m_used);
			return sval.Build();
		}
		
		void Load(SValue@ data)
		{
			m_used = data.GetBoolean();
		}
		
		ITooltip@ GetTooltip() { return null; }
		UsableIcon GetIcon(Player@ player)
		{
			if (!CanUse(player))
				return Cross;

			return Generic;
		}

		int UsePriority() { return 0; }
		void NetUse(PlayerHusk@ player) { }
	}
}
