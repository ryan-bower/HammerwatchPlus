// pkg-mismatch probe: the check tools/build.py generates since update stamps (issue #24), for a
// package "stampnew" of an older update: library 000000000001, update 2026-10-01 0000000.
// HWP::Builds::Tell names it with its update; stampfake (Check.as) is one from before stamps.
namespace Modules
{
	class HWPPackage_stampnew : Module
	{
		HWPPackage_stampnew()
		{
			super("hwp-package-stampnew");
			HWP::Builds::Package("HWP-stampnew", "2026-10-01 0000000", "000000000001", HWP::LIB_STAMP);
			if (HWP::LIB_STAMP == "000000000001")
				HWP::Log("core", "package HWP-stampnew, library 000000000001, update 2026-10-01 0000000");
			else
			{
				HWP::LogError("core", "package HWP-stampnew was built with library 000000000001 but library "
					+ HWP::LIB_STAMP + " loaded: another HammerwatchPlus package is older or newer; update them all");
				HWP::Packages::Mismatch("HWP-stampnew");
			}
		}
	}
}
