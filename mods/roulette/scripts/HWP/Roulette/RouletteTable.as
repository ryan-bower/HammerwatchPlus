// HWP::Roulette - a single-zero (European) roulette table for the whole lobby: the wheel on
// a tavern table (doodads/hwp/hwp_roulette_wheel.unit, placed by RouletteModule.as) opens
// the table's window (RouletteMenu.as).
//
// The host runs the rounds: BETTING (BET_MS), SPINNING (SPIN_MS, the number is drawn when
// the spin starts) and RESULT (RESULT_MS), then the next round. Every phase change goes to
// the lobby as "roulette.state" {round, phase, ms, result, players, staked}; each machine
// counts the phase down itself, and a client that opens the window asks for it
// ("roulette.hello"). The host keeps its own copy of the round (h_*): Broadcast hands the
// host its own message at once, and the g_* state changes only there (OnState), on every
// machine alike. A round runs only while the host is in town; leaving town (a run
// starting) refunds what is still on the table. A player's chips in one round are capped
// by the setting roulette.max_stake (1,000,000).
//
// Bets are each player's own: a chip comes out of the local player's gold when it is
// placed (Clear gives it back while the betting is open) and the local machine pays its
// own winning bets when the result lands. The host only learns each player's total
// ("roulette.stake") to show who is playing; it cannot check anyone's gold.
//
// The 157 bets of the table, at true odds (the zero is the 2.70 % house edge): 37
// straights 35:1, 60 splits 17:1 (the zero's three too), 12 streets and the two trios
// (0-1-2, 0-2-3) 11:1, 22 corners and the first four (0-1-2-3) 8:1, 11 six lines 5:1,
// dozens and columns 2:1, red / black, odd / even, low / high 1:1.
//
// The payout bonus: what a winning bet pays over its stake is raised by the player's
// Luck (core HWP::Luck, +1 % per point) and gold find (their gold gain modifiers: gear,
// trinkets, the Lucky Leaf herb's +5 %; New Game+ gold is not counted), Bonus() and
// BonusText(). Past about +2.8 % the table is in the player's favour.
namespace HWP
{
	namespace Roulette
	{
		const int BET_MS = 20000;
		const int SPIN_MS = 5000;
		const int RESULT_MS = 5000;
		const int NUMBERS = 37;
		const array<int> WHEEL = { 0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8,
			23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26 };
		const array<int> REDS = { 1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36 };
		const array<int> CHIPS = { 100, 1000, 10000, 100000 };
		const int HISTORY = 12;
		const string WHEEL_UNIT = "doodads/hwp/hwp_roulette_wheel.unit";

		int MaxStake() { return max(100, HWP::Settings::GetInt("roulette.max_stake", 1000000)); }

		enum Phase { Betting = 0, Spinning = 1, Result = 2, Closed = 3 }

		bool IsRed(int n) { return REDS.find(n) >= 0; }

		// one of the 157 bets: what it covers and what it pays (odds:1)
		class Bet
		{
			string key;
			string name;
			array<int> nums;
			int odds;
			Bet(const string &in k, const string &in n, array<int>@ c, int o) { key = k; name = n; nums = c; odds = o; }
			bool Covers(int n) { return nums.find(n) >= 0; }
		}

		array<Bet@> g_bets;

		string Nums(array<int>@ c)
		{
			string s;
			for (uint i = 0; i < c.length(); i++)
				s += (i > 0 ? "-" : "") + c[i];
			return s;
		}

		void Add(const string &in key, const string &in kind, array<int>@ c, int odds)
		{
			g_bets.insertLast(Bet(key, Resources::GetString(".hwp.roulette.bet." + kind, { { "nums", Nums(c) } }), c, odds));
		}

		void MakeBets()
		{
			if (g_bets.length() > 0)
				return;
			for (int n = 0; n <= 36; n++)
				Add("s:" + n, "straight", { n }, 35);
			for (int n = 1; n <= 33; n++)
				Add("sp:" + n + "-" + (n + 3), "split", { n, n + 3 }, 17);
			for (int n = 1; n <= 35; n++)
			{
				if (n % 3 != 0)
					Add("sp:" + n + "-" + (n + 1), "split", { n, n + 1 }, 17);
			}
			for (int n = 1; n <= 3; n++)
				Add("sp:0-" + n, "split", { 0, n }, 17);
			for (int n = 1; n <= 34; n += 3)
				Add("st:" + n, "street", { n, n + 1, n + 2 }, 11);
			Add("t:0-1-2", "trio", { 0, 1, 2 }, 11);
			Add("t:0-2-3", "trio", { 0, 2, 3 }, 11);
			for (int n = 1; n <= 32; n++)
			{
				if (n % 3 != 0)
					Add("c:" + n, "corner", { n, n + 1, n + 3, n + 4 }, 8);
			}
			Add("f4", "first_four", { 0, 1, 2, 3 }, 8);
			for (int n = 1; n <= 31; n += 3)
				Add("sl:" + n, "six_line", { n, n + 1, n + 2, n + 3, n + 4, n + 5 }, 5);
			for (int d = 0; d < 3; d++)
			{
				array<int> c;
				for (int n = d * 12 + 1; n <= d * 12 + 12; n++)
					c.insertLast(n);
				Add("d:" + (d + 1), "dozen" + (d + 1), c, 2);
			}
			for (int k = 1; k <= 3; k++)
			{
				array<int> c;
				for (int n = k; n <= 36; n += 3)
					c.insertLast(n);
				Add("col:" + k, "column" + k, c, 2);
			}
			array<int> red, black, odd, even, low, high;
			for (int n = 1; n <= 36; n++)
			{
				if (IsRed(n)) red.insertLast(n); else black.insertLast(n);
				if (n % 2 == 1) odd.insertLast(n); else even.insertLast(n);
				if (n <= 18) low.insertLast(n); else high.insertLast(n);
			}
			Add("red", "red", red, 1);
			Add("black", "black", black, 1);
			Add("odd", "odd", odd, 1);
			Add("even", "even", even, 1);
			Add("low", "low", low, 1);
			Add("high", "high", high, 1);
		}

		Bet@ Get(const string &in key)
		{
			MakeBets();
			for (uint i = 0; i < g_bets.length(); i++)
			{
				if (g_bets[i].key == key)
					return g_bets[i];
			}
			return null;
		}

		// ---- the table's state, the same on every machine

		int g_round = 0;
		Phase g_phase = Phase::Closed;
		int g_ms = 0;          // left in this phase, counted down locally
		int g_result = -1;     // this round's number, from the spin on
		int g_betPlayers = 0;  // players with chips down this round (host's count)
		int g_staked = 0;      // the lobby's chips on the table this round
		array<int> g_history;  // the last numbers, newest first
		bool g_open = false;   // the host is in town and runs rounds

		// ---- the local player's bets this round

		array<string> g_myKeys;
		array<int> g_myStakes;
		int g_myRound = -1;
		int g_lastWin = 0;     // what the last settled round paid back (stakes included)
		int g_lastStake = 0;
		string g_lastText;

		int MyStake(const string &in key)
		{
			int i = g_myKeys.find(key);
			return i < 0 ? 0 : g_myStakes[i];
		}

		int MyTotal()
		{
			int t = 0;
			for (uint i = 0; i < g_myStakes.length(); i++)
				t += g_myStakes[i];
			return t;
		}

		PlayerRecord@ Me() { return GetLocalPlayerRecord(); }

		int Gold()
		{
			auto rec = Me();
			return rec is null ? 0 : rec.GetMaterial(MaterialType::Gold);
		}

		// ---- the payout bonus

		float LuckBonus()
		{
			auto rec = Me();
			return rec is null ? 0.0f : max(0.0f, HWP::Luck::FactorRecord(rec) - 1.0f);
		}

		float GoldBonus()
		{
			auto rec = Me();
			if (rec is null)
				return 0.0f;
			auto mods = rec.GetModifiers();
			float mul = mods.MaterialGainMul(rec, MaterialType::Gold) * mods.MaterialGainMulMul(rec, MaterialType::Gold);
			return max(0.0f, mul - 1.0f);
		}

		float Bonus() { return LuckBonus() + GoldBonus(); }

		string Pct(float f) { return "" + int(f * 100.0f + 0.5f) + "%"; }

		string BonusText()
		{
			return Resources::GetString(".hwp.roulette.bonus", { { "total", Pct(Bonus()) },
				{ "luck", Pct(LuckBonus()) }, { "gold", Pct(GoldBonus()) } });
		}

		// what a winning stake pays back: the stake and its winnings, the winnings raised
		int Payout(int stake, int odds)
		{
			return stake + int(float(stake) * float(odds) * (1.0f + Bonus()));
		}

		// ---- placing chips (the local player, while the betting is open)

		bool CanBet() { return g_open && g_phase == Phase::Betting; }

		void ReportStake()
		{
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("round", g_round);
			b.PushInteger("total", MyTotal());
			b.PopDictionary();
			HWP::Net::Request("roulette.stake", b.Build());
		}

		string g_why; // why the last Place said no: a .hwp.roulette.no_* string

		bool Place(const string &in key, int chip)
		{
			auto bet = Get(key);
			auto rec = Me();
			if (g_myRound != g_round)
				ForgetBets();
			g_why = !CanBet() ? ".hwp.roulette.no_betting" : (bet is null || rec is null || chip <= 0) ? ".hwp.roulette.no_bet"
				: Gold() < chip ? ".hwp.roulette.no_gold" : MyTotal() + chip > MaxStake() ? ".hwp.roulette.no_max" : "";
			if (!g_why.isEmpty())
				return false;
			g_myRound = g_round;
			rec.GiveMaterial(MaterialType::Gold, -chip, true);
			int i = g_myKeys.find(key);
			if (i < 0)
			{
				g_myKeys.insertLast(key);
				g_myStakes.insertLast(chip);
			}
			else
				g_myStakes[i] += chip;
			HWP::Log("roulette", "round " + g_round + ": " + chip + " on " + key + " (" + MyStake(key) + " there, " + MyTotal() + " in all)");
			ReportStake();
			return true;
		}

		void ForgetBets()
		{
			g_myKeys.removeRange(0, g_myKeys.length());
			g_myStakes.removeRange(0, g_myStakes.length());
		}

		// every chip back to the player (Clear, or the table closing mid round)
		int Refund(const string &in why)
		{
			int t = MyTotal();
			auto rec = Me();
			if (t > 0 && rec !is null)
				rec.GiveMaterial(MaterialType::Gold, t, true);
			if (t > 0)
				HWP::Log("roulette", "round " + g_myRound + ": " + t + " back (" + why + ")");
			ForgetBets();
			if (why == "cleared")
				ReportStake();
			return t;
		}

		bool Clear()
		{
			if (!CanBet() || g_myRound != g_round || MyTotal() == 0)
				return false;
			Refund("cleared");
			return true;
		}

		// the result: the local player's bets pay or go
		void Settle()
		{
			if (g_myRound != g_round || g_myKeys.length() == 0)
				return;
			int staked = MyTotal(), won = 0;
			string hits;
			for (uint i = 0; i < g_myKeys.length(); i++)
			{
				auto bet = Get(g_myKeys[i]);
				if (bet is null || !bet.Covers(g_result))
					continue;
				int pay = Payout(g_myStakes[i], bet.odds);
				won += pay;
				hits += (hits.isEmpty() ? "" : ", ") + g_myKeys[i] + " " + pay;
			}
			auto rec = Me();
			if (won > 0 && rec !is null)
				rec.GiveMaterial(MaterialType::Gold, won, true);
			g_lastWin = won;
			g_lastStake = staked;
			if (won > 0)
				g_lastText = Resources::GetString(".hwp.roulette.won", { { "won", won }, { "staked", staked }, { "num", g_result } });
			else
				g_lastText = Resources::GetString(".hwp.roulette.lost", { { "staked", staked }, { "num", g_result } });
			HWP::Log("roulette", "round " + g_round + " landed " + g_result + ": staked " + staked + ", paid " + won
				+ " (bonus " + Pct(Bonus()) + ")" + (hits.isEmpty() ? "" : ": " + hits));
			ForgetBets();
		}

		// ---- the host's rounds (h_*, see the top)

		bool h_open = false;
		int h_round = 0;
		Phase h_phase = Phase::Closed;
		int h_ms = 0;
		int h_result = -1;
		array<uint8> g_stakePeers;
		array<int> g_stakeTotals;
		bool g_spinNow = false;
		int g_forced = -1;   // hwp roulette spin <n> (cheats): the host's next number

		SValue@ State()
		{
			int players = 0, staked = 0;
			for (uint i = 0; i < g_stakeTotals.length(); i++)
			{
				if (g_stakeTotals[i] > 0)
				{
					players++;
					staked += g_stakeTotals[i];
				}
			}
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("round", h_round);
			b.PushInteger("phase", int(h_phase));
			b.PushInteger("ms", h_ms);
			b.PushInteger("result", h_result);
			b.PushInteger("players", players);
			b.PushInteger("staked", staked);
			b.PopDictionary();
			return b.Build();
		}

		void HostEnter(Phase p)
		{
			h_phase = p;
			if (p == Phase::Betting)
			{
				h_round++;
				h_ms = BET_MS;
				h_result = -1;
				g_spinNow = false;
				g_stakePeers.removeRange(0, g_stakePeers.length());
				g_stakeTotals.removeRange(0, g_stakeTotals.length());
			}
			else if (p == Phase::Spinning)
			{
				h_ms = SPIN_MS;
				h_result = g_forced >= 0 && g_forced < NUMBERS ? g_forced : randi(NUMBERS);
				g_forced = -1;
			}
			else if (p == Phase::Result)
				h_ms = RESULT_MS;
			HWP::Net::Broadcast("roulette.state", State());
		}

		// HWPRouletteModule.UpdateFrame on the host, in town
		void HostUpdate(int ms)
		{
			if (!h_open)
			{
				h_open = true;
				HostEnter(Phase::Betting);
				return;
			}
			h_ms = max(0, h_ms - ms);
			if (h_phase == Phase::Betting && g_spinNow)
				h_ms = 0;
			if (h_ms > 0)
				return;
			if (h_phase == Phase::Betting)
				HostEnter(Phase::Spinning);
			else if (h_phase == Phase::Spinning)
				HostEnter(Phase::Result);
			else
				HostEnter(Phase::Betting);
		}

		void HostClose()
		{
			h_open = false;
			h_phase = Phase::Closed;
		}

		// a player's chips this round: the lobby sees who plays and how much is down
		void OnStake(uint8 peer, SValue@ data)
		{
			if (!h_open || HWP::SV::Int(data, "round", -1) != h_round || h_phase != Phase::Betting)
				return;
			int i = g_stakePeers.find(peer);
			if (i < 0)
			{
				g_stakePeers.insertLast(peer);
				g_stakeTotals.insertLast(0);
				i = int(g_stakePeers.length()) - 1;
			}
			g_stakeTotals[i] = max(0, HWP::SV::Int(data, "total", 0));
			HWP::Net::Broadcast("roulette.state", State());
		}

		// a client opened the window: the round as it is now
		void OnHello(uint8 peer, SValue@ data)
		{
			if (h_open)
				HWP::Net::Send(peer, "roulette.state", State());
		}

		// Spin now: solo only (a lobby waits for the timer, so nobody is rushed)
		bool CanSpinNow() { return CanBet() && Lobby() <= 1 && MyTotal() > 0; }

		void OnSpinNow(uint8 peer, SValue@ data)
		{
			if (Lobby() <= 1 && h_phase == Phase::Betting)
				g_spinNow = true;
		}

		int Lobby()
		{
			int n = 0;
			for (uint i = 0; i < ::g_players.length(); i++)
			{
				if (::g_players[i] !is null && ::g_players[i].peer != 255)
					n++;
			}
			return n;
		}

		// the wheels on the tavern tables turn fast while the ball runs
		void Wheels(bool fast)
		{
			auto prod = Resources::GetUnitProducer(WHEEL_UNIT);
			if (prod is null)
				return;
			auto units = g_scene.FetchAllUnitsOfType(prod);
			for (uint i = 0; i < units.length(); i++)
				units[i].SetUnitScene(fast ? "spin" : "idle", false);
		}

		// ---- every machine

		void OnState(SValue@ data)
		{
			int round = HWP::SV::Int(data, "round", 0);
			Phase p = Phase(HWP::SV::Int(data, "phase", 0));
			g_ms = HWP::SV::Int(data, "ms", 0);
			g_betPlayers = HWP::SV::Int(data, "players", 0);
			g_staked = HWP::SV::Int(data, "staked", 0);
			g_open = true;
			// chips from a round this machine missed the end of (a lost message): back
			if (g_myRound >= 0 && g_myRound != round && g_myKeys.length() > 0)
				Refund("missed round " + g_myRound);
			bool landed = p == Phase::Result && (g_phase != Phase::Result || g_round != round);
			if (p != g_phase)
				Wheels(p == Phase::Spinning);
			if (p == Phase::Spinning && g_phase != Phase::Spinning)
				g_spinFrom = g_history.length() > 0 ? WHEEL.find(g_history[0]) : 0;
			g_round = round;
			g_phase = p;
			g_result = HWP::SV::Int(data, "result", -1);
			if (landed && g_result >= 0)
			{
				g_history.insertAt(0, g_result);
				if (g_history.length() > uint(HISTORY))
					g_history.removeLast();
				Settle();
			}
		}

		void Tick(int ms)
		{
			if (g_ms > 0)
				g_ms = max(0, g_ms - ms);
		}

		// out of town (a run starting, the game closing to the menu): the table shuts
		void Close()
		{
			if (Network::IsServer())
				HostClose();
			if (MyTotal() > 0)
				Refund("the table closed");
			g_open = false;
			g_phase = Phase::Closed;
			g_ms = 0;
		}

		// hwp roulette: the table's state. bet <key> <gold>: a chip, as a click on the board
		// would place it; clear: the chips back. Cheats, host: spin <n> lands the ball on n
		// and ends the betting now.
		void Cmd(array<string>@ args)
		{
			if (args.length() >= 3 && args[0] == "bet")
			{
				bool ok = Place(args[1], parseInt(args[2]));
				HWP::Commands::Reply(ok ? "bet " + args[2] + " on " + args[1] + " (" + MyTotal() + " down)"
					: "no bet: " + Resources::GetString(g_why));
				return;
			}
			if (args.length() >= 1 && args[0] == "clear")
			{
				HWP::Commands::Reply(Clear() ? "cleared" : "nothing to clear");
				return;
			}
			if (args.length() >= 2 && args[0] == "spin")
			{
				if (!HWP::Cheats::On())
					return;
				if (!Network::IsServer())
				{
					HWP::Commands::Reply("host only");
					return;
				}
				g_forced = parseInt(args[1]);
				g_spinNow = true;
				HWP::Commands::Reply("the ball lands on " + g_forced);
				return;
			}
			string mine;
			for (uint i = 0; i < g_myKeys.length(); i++)
				mine += (i > 0 ? ", " : "") + g_myKeys[i] + " " + g_myStakes[i];
			HWP::Commands::Reply("roulette: round " + g_round + ", phase " + int(g_phase) + ", " + (g_ms / 1000) + " s left, result "
				+ g_result + ", " + g_betPlayers + " player(s), " + g_staked + " staked; mine: " + (mine.isEmpty() ? "none" : mine)
				+ "; bonus " + Pct(Bonus()) + " (luck " + Pct(LuckBonus()) + ", gold " + Pct(GoldBonus()) + "); last "
				+ g_lastWin + " of " + g_lastStake + "; history " + Nums(g_history) + "; " + g_bets.length() + " bets");
		}

	}
}
