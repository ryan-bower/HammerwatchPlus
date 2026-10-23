// Dev Arena RNG reseed: is a fixed-seed bench possible? The engine's global RNG is drawn from
// every frame (RE_NOTES 2026-10-18, rand-frames 20261018-161957), so srand(seed) only fixes
// what combat draws if the engine draws the same amount each frame. A probe: srand now, then
// take n randi(1000) draws `frames` gameplay frames later. Two probes with one seed and one
// delay that agree say the frame draws are steady; disagreeing ones say they are not.
namespace HWP
{
namespace DevArena
{
	uint g_rngSeed;
	int g_rngFramesLeft = -1;  // >= 0 while a probe waits
	int g_rngFrames;
	array<int> g_rngDraws;
	int g_rngProbes;

	void StartRng(uint seed, int frames)
	{
		g_rngSeed = seed;
		g_rngFrames = frames;
		g_rngDraws.resize(0);
		srand(seed);
		g_rngFramesLeft = frames;
		if (frames == 0)
			TakeRng();
	}

	void TakeRng()
	{
		for (uint i = 0; i < 8; i++)
			g_rngDraws.insertLast(randi(1000));
		g_rngFramesLeft = -1;
		g_rngProbes++;
		HWP::Log("devarena", "rng seed " + g_rngSeed + " +" + g_rngFrames + " frames: " + g_rngDraws[0]
			+ "," + g_rngDraws[1] + "," + g_rngDraws[2] + "," + g_rngDraws[3]);
	}

	void TickRng(bool paused)
	{
		if (paused || g_rngFramesLeft < 0)
			return;
		if (g_rngFramesLeft == 0)
			TakeRng();
		else
			g_rngFramesLeft--;
	}
}
}
