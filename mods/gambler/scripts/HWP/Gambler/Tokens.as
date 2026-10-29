// Bet tokens, per character (HWP data bag "bet_tokens", the key core's market used, so
// older saves keep theirs). The gambler buys fish for them and rerolls gear for them; it
// registers them as the market's currency (core Market.as SetCurrency), so fish sell for
// tokens wherever wares are sold (the pirate, `hwp sell`). Without the gambler they sell
// for gold.
namespace HWP
{
	namespace Gambler
	{
		const string KEY_TOKENS = "bet_tokens";

		int Tokens(PlayerRecord@ rec)
		{
			if (rec is null)
				return 0;
			return HWP::SaveData::Player(rec).GetInt(KEY_TOKENS);
		}

		void AddTokens(PlayerRecord@ rec, int n)
		{
			if (rec is null)
				return;
			int t = Tokens(rec) + n;
			auto bag = HWP::SaveData::Player(rec);
			if (t <= 0)
				bag.Remove(KEY_TOKENS);
			else
				bag.SetInt(KEY_TOKENS, t);
		}

		// false (and nothing spent) when the player has fewer than n
		bool SpendTokens(PlayerRecord@ rec, int n)
		{
			if (rec is null || n < 0 || Tokens(rec) < n)
				return false;
			AddTokens(rec, -n);
			return true;
		}

		class BetTokens : HWP::Market::Currency
		{
			int Held(PlayerRecord@ rec) { return Tokens(rec); }
			void Add(PlayerRecord@ rec, int n) { AddTokens(rec, n); }

			string Amount(int n, bool brief)
			{
				return Resources::GetString(brief ? ".hwp.gambler.amount_short" : ".hwp.gambler.amount", { { "n", n } });
			}

			string Status(PlayerRecord@ rec)
			{
				return Resources::GetString(".hwp.gambler.token_count", { { "n", Tokens(rec) } });
			}
		}

		void CmdTokens(array<string>@ args)
		{
			if (!HWP::Cheats::On())
				return;
			auto plr = HWP::Cheats::Me();
			if (plr is null)
				return;
			int amount = HWP::Cheats::IntArg(args, 0, 10);
			AddTokens(plr, amount);
			HWP::Cheats::Reply("gave " + amount + " bet tokens (" + Tokens(plr) + ")");
		}

		void InitTokens()
		{
			HWP::Market::SetCurrency(BetTokens());
			HWP::Commands::Register("tokens", "[n]  (cheat) gain bet tokens, default 10", HWP::Commands::Handler(CmdTokens));
		}
	}
}
