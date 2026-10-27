// HWP::HiddenClasses - classes left out of the create-character list (core's
// CreateCharacterClass.as). A module calls HWP::HideClass("<id>") from its
// constructor, which runs before the menu builds the list. Characters already
// made with a hidden class still load and play; only new ones can't pick it.
namespace HWP
{
	array<uint> g_hiddenClasses;

	void HideClass(const string &in id)
	{
		uint hash = HashString(id);
		if (g_hiddenClasses.find(hash) < 0)
			g_hiddenClasses.insertLast(hash);
	}

	bool IsClassHidden(uint idHash)
	{
		return g_hiddenClasses.find(idHash) >= 0;
	}
}
