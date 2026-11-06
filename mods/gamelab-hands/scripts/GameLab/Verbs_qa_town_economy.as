// Read-only engine inputs, independent of optional HWP module functions.
// No calls to Roulette::Bonus/Payout, no setters, no production event hooks.
namespace GameLab
{
    void VerbQATownEconomyInputs(const string &in id, array<string>@ args)
    {
        auto rec = GetLocalPlayerRecord();
        if (rec is null || args.length() != 0)
        {
            Fail(id, "usage: economyinputs; requires a local record");
            return;
        }
        float luck = 0;
        uint luckCount = 0;
        for (uint i = 0; i < rec.currStats.m_customStats.length(); i++)
        {
            auto stat = rec.currStats.m_customStats[i];
            if (stat !is null && stat.id == "hwp-luck" && stat.svalue !is null)
            {
                luck = stat.svalue.GetFloat();
                luckCount++;
            }
        }
        if (luckCount > 1)
        {
            Fail(id, "duplicate hwp-luck entries; independent input contract refused");
            return;
        }
        auto modifiers = rec.GetModifiers();
        float goldA = modifiers.MaterialGainMul(rec, MaterialType::Gold);
        float goldB = modifiers.MaterialGainMulMul(rec, MaterialType::Gold);
        Emit(Reply(id, true).Int("gold", rec.GetMaterial(MaterialType::Gold))
            .Int("luckEntries", luckCount)
            .Raw("luck", formatFloat(double(luck), "", 0, 17))
            .Raw("goldMul", formatFloat(double(goldA), "", 0, 17))
            .Raw("goldMulMul", formatFloat(double(goldB), "", 0, 17)));
    }
}
namespace Modules
{
    class GameLabTownEconomyVerbs : Module
    {
        GameLabTownEconomyVerbs()
        {
            super("gamelab-town-economy-verbs");
            GameLab::RegisterVerb("economyinputs", "", GameLab::Verb(GameLab::VerbQATownEconomyInputs));
        }
    }
}
