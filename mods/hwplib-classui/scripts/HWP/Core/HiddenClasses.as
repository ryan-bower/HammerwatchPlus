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

	// a module turned back on (its settings page switch) offers the class again
	void ShowClass(const string &in id)
	{
		int i = g_hiddenClasses.find(HashString(id));
		if (i >= 0)
			g_hiddenClasses.removeAt(uint(i));
	}

	bool IsClassHidden(uint idHash)
	{
		return g_hiddenClasses.find(idHash) >= 0;
	}
}
