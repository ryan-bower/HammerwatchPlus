namespace WorldScript
{
	[WorldScript color="255 255 102" icon="system/icons.png;352;32;32;32"]
	class SecretFound
	{
		vec3 Position; // HWP laststats: the fallback for who opened it (the nearest player)

		// HWP laststats: vanilla added secrets-found to every machine's local player. The host
		// picks the player who opened the secret (HWP::LastStats::SecretOpener, Secrets.as) and
		// sends the peer along; only that player's run and character stats count it, the town's
		// accomplishment counter still counts it on every machine.
		SValue@ ServerExecute()
		{
			int peer = HWP::LastStats::SecretOpener(Position);
			HWP::LastStats::CreditSecret(peer);
			SValueBuilder b;
			b.PushDictionary();
			b.PushInteger("peer", peer);
			b.PopDictionary();
			return b.Build();
		}

		void ClientExecute(SValue@ val)
		{
			HWP::LastStats::CreditSecret(val is null ? -1 : HWP::SV::Int(val, "peer", -1));
		}
	}
}
