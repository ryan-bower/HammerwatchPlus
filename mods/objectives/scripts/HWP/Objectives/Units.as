// The objective units' behaviours (doodads/hwp/objective_door.unit,
// objective_switch.unit, objective_exit_switch.unit). Every machine has the
// floor's units, so each behaviour registers itself in HWP::Objectives on
// construction and is found again by position when the host's
// objectives.opened event names it (ObjectivesModule.as).
//
// A switch is an IUsable like a chest: the sensor circle adds it to the
// player's usables, the use key runs the vanilla use path (Player.as: the
// host runs Use, a client sends UseUnitSecure to the host, which runs NetUse
// and echoes UseUnit to everyone). Only the host acts on a use: it tells
// HWP::Objectives, which broadcasts what opened; the echo on a client does
// nothing by itself, so a late or lost echo cannot desync the floor.

class HWPObjectiveDoor
{
	UnitPtr m_unit;
	bool m_open = false;
	bool m_init = false;

	HWPObjectiveDoor(UnitPtr unit, SValue& params)
	{
		m_unit = unit;
		HWP::Objectives::g_doors.insertLast(this);
	}

	void Update(int dt)
	{
		if (m_init)
			return;
		m_init = true;
		if (!m_open && m_unit.IsValid())
			m_unit.SetUnitScene("locked", true);
	}

	vec2 Pos() { return m_unit.IsValid() ? xy(m_unit.GetPosition()) : vec2(); }

	void Open()
	{
		if (m_open)
			return;
		m_open = true;
		m_init = true;
		if (m_unit.IsValid() && !m_unit.IsDestroyed())
			m_unit.SetUnitScene("open", true);
	}
}

class HWPObjectiveSwitch : IUsable
{
	UnitPtr m_unit;
	string m_kind; // "vault" or "exit"
	string m_scene; // the scene last set: left, marked (map icon) or right
	bool m_used = false;
	bool m_init = false;

	HWPObjectiveSwitch(UnitPtr unit, SValue& params)
	{
		m_unit = unit;
		m_kind = GetParamString(unit, params, "kind", false, "vault");
		HWP::Objectives::g_switches.insertLast(this);
	}

	void Update(int dt)
	{
		if (m_init)
			return;
		m_init = true;
		// "marked" is "left" with the map icon (the Marked Switches alteration)
		if (!m_used && m_unit.IsValid())
		{
			m_scene = HWP::Objectives::SwitchesMarked() ? "marked" : "left";
			m_unit.SetUnitScene(m_scene, true);
		}
	}

	vec2 Pos() { return m_unit.IsValid() ? xy(m_unit.GetPosition()) : vec2(); }

	// the host said so (objectives.opened / objectives.state)
	void Flip()
	{
		if (m_used)
			return;
		m_used = true;
		m_init = true;
		if (m_unit.IsValid() && !m_unit.IsDestroyed())
		{
			m_scene = "right";
			m_unit.SetUnitScene(m_scene, true);
		}
	}

	void Collide(UnitPtr unit, vec2 pos, vec2 normal, Fixture@ fxSelf, Fixture@ fxOther)
	{
		Player@ player = cast<Player>(unit.GetScriptBehavior());
		if (player is null)
			return;
		if (fxSelf.IsSensor())
			player.AddUsable(this);
	}

	void EndCollision(UnitPtr unit, Fixture@ fxSelf, Fixture@ fxOther)
	{
		Player@ player = cast<Player>(unit.GetScriptBehavior());
		if (player is null)
			return;
		if (fxSelf.IsSensor())
			player.RemoveUsable(this);
	}

	UnitPtr GetUseUnit() { return m_unit; }

	bool CanUse(PlayerBase@ player)
	{
		return !m_used && m_unit.IsValid() && !m_unit.IsDestroyed();
	}

	void Use(PlayerBase@ player)
	{
		if (m_used || !m_unit.IsValid())
			return;
		if (Network::IsServer())
			HWP::Objectives::HostSwitchUsed(this, player);
		// a client: the host's objectives.opened flips this switch
	}

	void NetUse(PlayerHusk@ player)
	{
		Use(player);
	}

	UsableIcon GetIcon(Player@ player)
	{
		if (!CanUse(player))
			return UsableIcon::None;
		return UsableIcon::Button;
	}

	ITooltip@ GetTooltip() { return null; }
	int UsePriority() { return 0; }
	bool IsInside(UnitPtr unit) { return m_unit.IsColliding(unit); }
}
