// Separately registered native calibration. Ephemeral SValues only: no player,
// inventory, resource, input, settings, save, RNG or primary-codec changes.
namespace GameLab
{
    // This engine disallows primitive &inout parameters. Keep cumulative parse
    // status in one local script object shared by scalar/vector helper calls.
    class QACalParseState
    {
        bool complete = true;
    }

    double QACalDouble(const string &in text, QACalParseState@ parsed)
    {
        uint used = 0;
        double value = parseFloat(text, used);
        parsed.complete = parsed.complete && used == text.length();
        return value;
    }

    float QACalFloat(const string &in text, QACalParseState@ parsed)
    {
        return float(QACalDouble(text, parsed));
    }

    int64 QACalLong(const string &in text, QACalParseState@ parsed)
    {
        uint used = 0;
        int64 value = parseInt(text, 10, used);
        parsed.complete = parsed.complete && used == text.length();
        return value;
    }

    string QACalString(uint size)
    {
        string value;
        value.resize(size);
        for (uint i = 0; i < size; i++) value[i] = uint8(65);
        return value;
    }

    SValue@ QACalValue(const string &in name, QACalParseState@ parsed, uint &out nodesStart, string &out input)
    {
        parsed.complete = true; nodesStart = 0; input = "";
        SValueBuilder b;
        if (name == "f32_zero") { input = "0.0"; b.PushFloat(QACalFloat(input, parsed)); return b.Build(); }
        if (name == "f32_negzero") { input = "-0.0"; b.PushFloat(QACalFloat(input, parsed)); return b.Build(); }
        if (name == "f32_subnormal") { input = "1.401298464324817e-45"; b.PushFloat(QACalFloat(input, parsed)); return b.Build(); }
        if (name == "f32_min_normal") { input = "1.1754943508222875e-38"; b.PushFloat(QACalFloat(input, parsed)); return b.Build(); }
        if (name == "f32_max") { input = "3.4028234663852886e38"; b.PushFloat(QACalFloat(input, parsed)); return b.Build(); }
        if (name == "f32_negmax") { input = "-3.4028234663852886e38"; b.PushFloat(QACalFloat(input, parsed)); return b.Build(); }
        if (name == "f32_repr") { input = "0.1"; b.PushFloat(QACalFloat(input, parsed)); return b.Build(); }
        if (name == "f32_adjacent_a") { input = "0.12345679104328156"; b.PushFloat(QACalFloat(input, parsed)); return b.Build(); }
        if (name == "f32_adjacent_b") { input = "0.12345679849386215"; b.PushFloat(QACalFloat(input, parsed)); return b.Build(); }
        if (name == "f32_nan") { input = "nan"; b.PushFloat(QACalFloat(input, parsed)); return b.Build(); }
        if (name == "f32_inf") { input = "inf"; b.PushFloat(QACalFloat(input, parsed)); return b.Build(); }
        if (name == "f64_zero") { input = "0.0"; b.PushDouble(QACalDouble(input, parsed)); return b.Build(); }
        if (name == "f64_negzero") { input = "-0.0"; b.PushDouble(QACalDouble(input, parsed)); return b.Build(); }
        if (name == "f64_subnormal") { input = "4.9406564584124654e-324"; b.PushDouble(QACalDouble(input, parsed)); return b.Build(); }
        if (name == "f64_min_normal") { input = "2.2250738585072014e-308"; b.PushDouble(QACalDouble(input, parsed)); return b.Build(); }
        if (name == "f64_max") { input = "1.7976931348623157e308"; b.PushDouble(QACalDouble(input, parsed)); return b.Build(); }
        if (name == "f64_negmax") { input = "-1.7976931348623157e308"; b.PushDouble(QACalDouble(input, parsed)); return b.Build(); }
        if (name == "f64_repr") { input = "0.1"; b.PushDouble(QACalDouble(input, parsed)); return b.Build(); }
        if (name == "f64_adjacent") { input = "1.0000000000000002"; b.PushDouble(QACalDouble(input, parsed)); return b.Build(); }
        if (name == "f64_nan") { input = "nan"; b.PushDouble(QACalDouble(input, parsed)); return b.Build(); }
        if (name == "f64_inf") { input = "inf"; b.PushDouble(QACalDouble(input, parsed)); return b.Build(); }
        if (name == "f64_neginf") { input = "-inf"; b.PushDouble(QACalDouble(input, parsed)); return b.Build(); }

        if (name == "null") { b.PushNull(); return b.Build(); }
        if (name == "true") { b.PushBoolean(true); return b.Build(); }
        if (name == "false") { b.PushBoolean(false); return b.Build(); }
        if (name == "i32_min") { b.PushInteger(-2147483647 - 1); return b.Build(); }
        if (name == "i32_max") { b.PushInteger(2147483647); return b.Build(); }
        if (name == "i64_min") { input = "-9223372036854775808"; b.PushLong(QACalLong(input, parsed)); return b.Build(); }
        if (name == "i64_max") { input = "9223372036854775807"; b.PushLong(QACalLong(input, parsed)); return b.Build(); }
        if (name == "vec2") { b.PushVector2(vec2(QACalFloat("0.12345679104328156", parsed), QACalFloat("-0.0", parsed))); return b.Build(); }
        if (name == "vec3") { b.PushVector3(vec3(QACalFloat("1.401298464324817e-45", parsed), QACalFloat("0.12345679849386215", parsed), -1.0f)); return b.Build(); }
        if (name == "vec4") { b.PushVector4(vec4(QACalFloat("3.4028234663852886e38", parsed), QACalFloat("1.1754943508222875e-38", parsed), 0.0f, QACalFloat("-0.0", parsed))); return b.Build(); }
        if (name == "ivec2") { b.PushIVector2(ivec2(-2147483647 - 1, 2147483647)); return b.Build(); }
        if (name == "ivec3") { b.PushIVector3(ivec3(-1, 0, 1)); return b.Build(); }
        if (name == "ivec4") { b.PushIVector4(ivec4(-2147483647 - 1, -1, 1, 2147483647)); return b.Build(); }
        if (name == "byte_string_key")
        {
            string bytes; bytes.resize(5);
            bytes[0] = uint8(0); bytes[1] = uint8(1); bytes[2] = uint8(10);
            bytes[3] = uint8(92); bytes[4] = uint8(255);
            b.PushDictionary(); b.PushString(bytes, bytes); b.PopDictionary();
            return b.Build();
        }
        if (name == "depth16" || name == "depth17")
        {
            int depth = name == "depth16" ? 16 : 17;
            for (int i = 0; i < depth; i++) b.PushArray();
            b.PushNull();
            for (int i = 0; i < depth; i++) b.PopArray();
            return b.Build();
        }
        if (name == "array128" || name == "array129")
        {
            int count = name == "array128" ? 128 : 129;
            b.PushArray(); for (int i = 0; i < count; i++) b.PushNull(); b.PopArray();
            return b.Build();
        }
        if (name == "dict128" || name == "dict129")
        {
            int count = name == "dict128" ? 128 : 129;
            b.PushDictionary(); for (int i = 0; i < count; i++) b.PushNull("k" + i); b.PopDictionary();
            return b.Build();
        }
        if (name == "string1024" || name == "string1025")
        { b.PushString(QACalString(name == "string1024" ? 1024 : 1025)); return b.Build(); }
        if (name == "text5" || name == "text6")
        {
            int count = name == "text5" ? 5 : 6;
            b.PushArray();
            for (int i = 0; i < count; i++) b.PushString(QACalString(1024));
            b.PopArray(); return b.Build();
        }
        // A natural512-node minimal tree exceeds11000 text first. These two
        // explicit seeded-budget diagnostics exercise only the native counter
        // boundary, never pretend that the tree itself contains512 nodes.
        if (name == "seeded_nodes512" || name == "seeded_nodes513")
        {
            nodesStart = name == "seeded_nodes512" ? 511 : 512;
            b.PushNull(); return b.Build();
        }
        if (name == "unsupported_bytes")
        {
            auto fixture = Resources::GetSValue("tweak/gamelab/qa_item_transport_fixture.sval");
            if (fixture is null || fixture.GetType() != SValueType::Dictionary) return null;
            auto value = fixture.GetDictionaryEntry("unsupported");
            return value is null ? null : value.Copy(); // resource remains engine-owned
        }
        return null;
    }

    void VerbQAItemTransportCalibrate(const string &in id, array<string>@ args)
    {
        if (args.length() != 1)
        { Fail(id, "usage: qa_item_transport_calibrate <exact calibration case>"); return; }
        QACalParseState@ parsed = QACalParseState();
        uint nodesStart;
        string input;
        SValue@ value = QACalValue(args[0], parsed, nodesStart, input);
        if (value is null)
        { Fail(id, "unknown calibration case or missing owned ByteArray resource"); return; }
        auto type = value.GetType();
        string sourceType = Reflect::TypeOf(type).GetEnumName(int(type));
        QAItemTypedEncoder encoder; // exact reviewed primary codec, not a copy
        encoder.nodes = nodesStart;
        string typed = encoder.Value(value, 0);
        value.Delete();
        bool accepted = encoder.reason.isEmpty();
        Json result;
        result.Bool("accepted", accepted).Bool("complete", accepted).Bool("truncated", encoder.truncated)
            .Str("reason", encoder.reason).Int("nodes", encoder.nodes).Int("depth", encoder.deepest);
        if (accepted) result.Raw("typed", typed); // refused cases never emit partial data
        Emit(Reply(id, true).Str("schema", "gamelab.item-calibration.v1").Str("case", args[0])
            .Str("source_type", sourceType).Str("input", input).Bool("parsed_all", parsed.complete)
            .Int("nodes_start", nodesStart).Raw("result", result.Close()));
    }

    void Register_qa_item_identity_calibration()
    {
        RegisterVerb("qa_item_transport_calibrate", "<exact calibration case>", Verb(VerbQAItemTransportCalibrate));
    }
}
