// pkg-mismatch probe (gamelab/scenarios/pkg-mismatch.json): the package check module
// tools/build.py stamp_entries generates for every package, here for a package "stampfake" made
// with a library stamp no build has, as an older or newer package would be. It needs a real
// package beside it for HWP::LIB_STAMP and HWP::Packages.
namespace Modules
{
	class HWPPackage_stampfake : Module
	{
		HWPPackage_stampfake()
		{
			super("hwp-package-stampfake");
			if (HWP::LIB_STAMP == "000000000000")
				HWP::Log("core", "package HWP-stampfake, library 000000000000");
			else
			{
				HWP::LogError("core", "package HWP-stampfake was built with library 000000000000 but library "
					+ HWP::LIB_STAMP + " loaded: another HammerwatchPlus package is older or newer; update them all");
				HWP::Packages::Mismatch("HWP-stampfake");
			}
		}
	}
}
