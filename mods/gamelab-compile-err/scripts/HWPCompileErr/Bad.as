// compile-err probe: a call to a function the game does not have (as if an update renamed it)
namespace HWPCompileErr
{
	void Touch()
	{
		HWPNoSuchVanillaFunction(1);
	}
}
