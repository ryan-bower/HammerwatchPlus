// Read-only planner query: exactly the existing native Pilot.Repath, never
// installs an intent or writes input. A bounded point along its returned native
// polyline permits ordinary short walks and fresh geometry observation.
namespace GameLab
{
    void VerbQARouteLeg(const string &in id, array<string>@ args)
    {
        auto plr = GetLocalPlayer();
        if (plr is null || args.length() < 2 || args.length() > 3)
        {
            Fail(id, "usage: qa_routeleg <x> <y> [32..256 arc pixels]");
            return;
        }
        float limit = args.length() > 2 ? parseFloat(args[2]) : 128.0f;
        if (!(limit >= 32.0f && limit <= 256.0f))
        {
            Fail(id, "native leg arc bound must be32..256 pixels");
            return;
        }
        vec2 from = xy(plr.m_unit.GetPosition());
        vec2 to(parseFloat(args[0]), parseFloat(args[1]));
        PilotIntent query;
        query.goal = to;
        bool routed = Repath(query, from);
        auto path = query.path;
        auto j = Reply(id, true).Str("planner", "Pilot.Repath").Bool("routed", routed)
            .Num("fx", from.x).Num("fy", from.y).Num("tx", to.x).Num("ty", to.y)
            .Int("diameter", PATH_DIAMETER).Num("limit", limit)
            .Int("nodes", path is null ? 0 : int(path.length()));
        if (routed && path !is null && path.length() > 0)
        {
            float length = 0.0f;
            vec2 previous = from;
            vec2 leg = from;
            float legLength = 0.0f;
            for (uint i = 0; i < path.length(); i++)
            {
                float segment = dist(previous, path[i]);
                length += segment;
                if (legLength < limit && segment > 0.0f)
                {
                    float take = min(segment, limit - legLength);
                    leg = previous + (path[i] - previous) * (take / segment);
                    legLength += take;
                }
                previous = path[i];
            }
            vec2 last = path[path.length() - 1];
            j.Num("length", length).Num("lastX", last.x).Num("lastY", last.y)
                .Bool("complete", dist(last, to) <= 12.0f)
                .Num("legX", leg.x).Num("legY", leg.y).Num("legLength", legLength)
                .Bool("legClipped", length > limit);
        }
        Emit(j);
    }
    void Register_qa_routeleg()
    {
        RegisterVerb("qa_routeleg", "<x> <y> [32..256 arc pixels]", Verb(VerbQARouteLeg));
    }
}
