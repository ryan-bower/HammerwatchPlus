// dup-path probe: this mod's own file, which reads the shared ones.
namespace Modules
{
	class GameLabDupBModule : Module
	{
		GameLabDupBModule()
		{
			super("gamelab-dup-b");
			HWPDup::Same s;
			print("[GL-dup] b sees WHO=" + HWPDup::WHO + " lang=" + Resources::GetString(".hwp.dup.who") + " same=" + s.v);
		}
	}
}
