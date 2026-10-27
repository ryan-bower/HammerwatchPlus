// HWP::Packages - HammerwatchPlus packages of different builds enabled together.
// Every package carries the library at the same paths and the game keeps the first copy of
// each path, so an older package beside a newer one runs on a mix of the two builds. Each
// package's generated check module (tools/build.py stamp_entries) compares the library build
// it was made with to the one the game loaded and calls Mismatch when they differ; the core
// module tells the player on every town visit until the packages match again.
//
// Packages of other builds call Mismatch: never rename it or change its signature.
namespace HWP
{
	namespace Packages
	{
		array<string> g_mismatched;

		void Mismatch(const string &in package)
		{
			if (g_mismatched.find(package) < 0)
				g_mismatched.insertLast(package);
		}

		void Tell()
		{
			if (g_mismatched.length() == 0)
				return;
			HWP::Commands::Reply(Resources::GetString(".hwp.packages.mismatch", { { "list", join(g_mismatched, ", ") } }));
		}
	}
}
