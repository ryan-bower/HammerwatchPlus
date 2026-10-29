// dup-path probe: this mod's own file, which reads the shared ones.
namespace Modules
{
	class GameLabDupAModule : Module
	{
		GameLabDupAModule()
		{
			super("gamelab-dup-a");
			HWPDup::Same s;
			print("[GL-dup] a sees WHO=" + HWPDup::WHO + " lang=" + Resources::GetString(".hwp.dup.who") + " same=" + s.v);
		}
	}
}
