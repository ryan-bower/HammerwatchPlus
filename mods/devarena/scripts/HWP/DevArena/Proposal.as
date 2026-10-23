// Auto-tuner proposals (docs/devarena/SPEC.md HP7, "Decided during build" 28). The tuner
// (gamelab/bots/devarena_autotune.py over tools/devarena/autotune.py) edits B with da-set,
// benches it with the Bench tab's Start button and, when a candidate meets its target, files it
// here with da-propose. Nothing is kept until the player says so: the Bench tab shows the
// proposal as PENDING with its bench evidence, and Accept (Keep B>A) or Discard (Discard B) there
// settles it. One proposal at a time; a new one replaces it.
namespace HWP
{
namespace DevArena
{
	int g_propVersion = -1;      // the proposed version (B when filed), -1 none
	int g_propBase = -1;         // A when filed
	int g_propBench;             // the bench its evidence came from
	string g_propNote;
	string g_propEvidence;       // that bench's bench-result json
	string g_propVerdict;        // "B better, A 323 B 391 dps, +21.0%"
	string g_propLast;           // "accepted v7", "discarded v7", "" none
	int g_proposals;

	bool HasProposal()
	{
		return g_propVersion >= 0;
	}

	string ProposalJson()
	{
		if (!HasProposal())
			return "null";
		return "{\"version\":" + g_propVersion + ",\"base\":" + g_propBase + ",\"bench\":" + g_propBench
			+ ",\"note\":" + GameLab::Quote(g_propNote) + ",\"evidence\":" + g_propEvidence + "}";
	}

	// "" when filed, else why not
	string Propose(const string &in note)
	{
		if (BenchRunning())
			return "a bench is running";
		if (g_slotB < 0)
			return "B is empty";
		if (g_benchResult == "" || g_sideB is null || g_sideB.version != g_slotB || g_sideA.version != g_slotA)
			return "the last bench was not A v" + g_slotA + " vs B v" + g_slotB + "; bench it first";
		g_propVersion = g_slotB;
		g_propBase = g_slotA;
		g_propBench = g_benchId;
		g_propNote = note;
		g_propEvidence = g_benchResult;
		g_propVerdict = g_benchVerdict + ", A " + int(Stats(g_sideA.dps).mean) + " B " + int(Stats(g_sideB.dps).mean)
			+ " dps, " + (g_cmpDelta > 0 ? "+" : "") + formatFloat(g_cmpDelta, "", 0, 1) + "%";
		g_propLast = "";
		g_proposals++;
		HWP::Log("devarena", "autotune-proposal " + ProposalJson());
		g_lastAction = "proposal: v" + g_propVersion + " (pending on the Bench tab)";
		return "";
	}

	// Accept keeps B (Keep B>A), Discard drops it (Discard B); either way the proposal goes.
	// Accept is refused when A or B moved since it was filed; Discard then only drops the note.
	void SettleProposal(bool accept)
	{
		if (!HasProposal())
		{
			g_lastError = "no pending proposal";
			return;
		}
		bool same = g_slotB == g_propVersion && g_slotA == g_propBase;
		if (accept && !same)
		{
			g_lastError = "A/B moved since the proposal (A v" + g_slotA + ", B v" + g_slotB + "); discard it";
			return;
		}
		if (accept)
			KeepB();
		else if (same)
			BenchDiscardB();
		string what = accept ? "accept" : "discard";
		HWP::Log("devarena", "autotune-" + what + " {\"version\":" + g_propVersion + ",\"bench\":" + g_propBench
			+ ",\"note\":" + GameLab::Quote(g_propNote) + "}");
		g_propLast = what + "ed v" + g_propVersion;
		g_lastAction = "proposal " + g_propLast;
		g_propVersion = -1;
	}

	// the Bench tab's PENDING section; drawn only while a proposal waits (or just settled)
	float LayoutProposal(Ui@ ui, float x, float y, float w)
	{
		float row = RowH();
		if (!HasProposal())
		{
			if (g_propLast != "")
			{
				ui.Text(x, y, "auto-tuner proposal " + g_propLast, COL_DIM);
				y += row + PAD;
			}
			return y;
		}
		y = Head(ui, x, y, "PENDING  auto-tuner proposal v" + g_propVersion);
		ui.Text(x, y, g_propNote, COL_TEXT);
		y += row;
		ui.Text(x, y, "evidence: bench #" + g_propBench + ", A v" + g_propBase + " vs B v" + g_propVersion + ", "
			+ g_propVerdict, COL_SUB);
		y += row;
		float hw = (w - 2) / 2;
		if (ui.Button("pacc", vec4(x, y, hw, row), "Accept (B>A)", COL_ON) && !BenchRunning())
			SettleProposal(true);
		if (ui.Button("pdis", vec4(x + hw + 2, y, hw, row), "Discard") && !BenchRunning())
			SettleProposal(false);
		return y + row + 1 + PAD;
	}

	// da-propose <note words...>: setup, the auto-tuner filing its candidate (what it would do
	// in the dock if it had hands). B must be the version the last bench measured against A.
	void VerbPropose(const string &in id, array<string>@ args)
	{
		string err = Propose(join(args, " "));
		if (err != "")
		{
			GameLab::Fail(id, err);
			return;
		}
		GameLab::Emit(GameLab::Reply(id, true).Int("version", g_propVersion).Int("base", g_propBase)
			.Int("bench", g_propBench).Int("proposals", g_proposals));
	}
}
}
