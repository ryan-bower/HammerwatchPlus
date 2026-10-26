// A mod action for the InstantiateClass spike: the engine's action loader builds it by name
// (Actions/IAction.as:282, InstantiateClass(cName, unit, params)) when a skill's action
// entry says "class": "HWP::DevArena::ProbeAction". It counts DoAction calls and logs them.
namespace HWP
{
namespace DevArena
{
	int g_probeBuilt;
	int g_probeFired;

	class ProbeAction : IAction
	{
		string m_tag;

		ProbeAction(UnitPtr unit, SValue& params)
		{
			m_tag = GetParamString(unit, params, "tag", false, "probe");
			g_probeBuilt++;
		}

		void Update(int dt, int cooldown) {}
		bool NeedNetParams() { return false; }
		void SetWeaponInformation(uint weapon) {}
		void CancelAction() {}

		bool DoAction(SValueBuilder@ builder, Actor@ owner, Actor@ target, vec2 pos, vec2 dir, float intensity)
		{
			g_probeFired++;
			HWP::Log("devarena", "probe action '" + m_tag + "' fired (" + g_probeFired + ")");
			return true;
		}

		bool NetDoAction(SValue@ param, Actor@ owner, vec2 pos, vec2 dir)
		{
			return true;
		}
	}
}
}
