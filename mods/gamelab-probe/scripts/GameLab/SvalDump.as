// sval <file>: the engine's own parse of an .sval data file (after its %defblock /
// %block / %if / %replace preprocessing), as JSON. Read-only. This is how
// gamecode/datatables/ is produced (tools/export_datatables.py): the engine is the
// parser, so the exports are what the game actually loaded, not a re-implementation.
//
// Script cannot write files, so the JSON goes to the log in chunks:
//   [GL] {"id":..,"ok":true,"file":..,"part":k,"of":n,"chunk":"<escaped JSON text>"}
// and the harness joins the chunks of one id in part order.
namespace GameLab
{
	const uint SVAL_CHUNK = 6000;

	string Vec(uint n, double x, double y, double z = 0, double w = 0)
	{
		string res = "[" + formatFloat(x, "", 0, 6) + "," + formatFloat(y, "", 0, 6);
		if (n > 2)
			res += "," + formatFloat(z, "", 0, 6);
		if (n > 3)
			res += "," + formatFloat(w, "", 0, 6);
		return res + "]";
	}

	string SvalJson(SValue@ sv, uint depth)
	{
		if (sv is null)
			return "null";
		if (depth > 64)
			return "{\"__truncated\":\"depth\"}";
		auto t = sv.GetType();
		if (t == SValueType::Null)
			return "null";
		if (t == SValueType::Boolean)
			return sv.GetBoolean() ? "true" : "false";
		if (t == SValueType::Integer)
			return "" + sv.GetInteger();
		if (t == SValueType::Long)
			return "" + sv.GetLong();
		if (t == SValueType::Float)
			return formatFloat(sv.GetFloat(), "", 0, 6);
		if (t == SValueType::String)
			return Quote(sv.GetString());
		if (t == SValueType::Array)
		{
			auto arr = sv.GetArray();
			string res = "[";
			for (uint i = 0; i < arr.length(); i++)
				res += (i > 0 ? "," : "") + SvalJson(arr[i], depth + 1);
			return res + "]";
		}
		if (t == SValueType::Dictionary)
		{
			auto keys = sv.GetDictionaryKeys();
			keys.sortAsc();
			string res = "{";
			for (uint i = 0; i < keys.length(); i++)
				res += (i > 0 ? "," : "") + Quote(keys[i]) + ":" + SvalJson(sv.GetDictionaryEntry(keys[i]), depth + 1);
			return res + "}";
		}
		if (t == SValueType::Vector2)
		{
			vec2 v = sv.GetVector2();
			return Vec(2, v.x, v.y);
		}
		if (t == SValueType::Vector4)
		{
			vec4 v = sv.GetVector4();
			return Vec(4, v.x, v.y, v.z, v.w);
		}
		if (t == SValueType::IVector2)
		{
			ivec2 v = sv.GetIVector2();
			return "[" + v.x + "," + v.y + "]";
		}
		// members the game's own scripts never name: dispatch on the enum's runtime name
		string name = Reflect::TypeOf(t).GetEnumName(int(t));
		if (name == "Vector3")
		{
			vec3 v = sv.GetVector3();
			return Vec(3, v.x, v.y, v.z);
		}
		if (name == "IVector3")
		{
			ivec3 v = sv.GetIVector3();
			return "[" + v.x + "," + v.y + "," + v.z + "]";
		}
		if (name == "IVector4")
		{
			ivec4 v = sv.GetIVector4();
			return "[" + v.x + "," + v.y + "," + v.z + "," + v.w + "]";
		}
		return "{\"__unsupported\":" + Quote(name) + "}";
	}

	// One entry of a parsed file: a dictionary's key, or the array element whose "id" is entry.
	SValue@ SvalEntry(SValue@ sv, const string &in entry)
	{
		if (sv.GetType() == SValueType::Dictionary)
			return sv.GetDictionaryEntry(entry);
		if (sv.GetType() != SValueType::Array)
			return null;
		auto arr = sv.GetArray();
		for (uint i = 0; i < arr.length(); i++)
		{
			if (arr[i] is null || arr[i].GetType() != SValueType::Dictionary)
				continue;
			auto e = arr[i].GetDictionaryEntry("id");
			if (e !is null && e.GetType() == SValueType::String && e.GetString() == entry)
				return arr[i];
		}
		return null;
	}

	// sval <file.sval>[:entry]: read-only. A datatable as the game parsed it, as JSON, sent in parts when long.
	// With :entry only that entry: a dictionary key, or the array element whose "id" matches.
	void VerbSval(const string &in id, array<string>@ args)
	{
		if (args.length() < 1)
		{
			Fail(id, "usage: sval <file.sval>[:entry]");
			return;
		}
		string file = args[0], entry = "";
		int colon = file.findFirst(".sval:");
		if (colon >= 0)
		{
			entry = file.substr(colon + 6);
			file = file.substr(0, colon + 5);
		}
		auto sv = Resources::GetSValue(file);
		if (sv is null)
		{
			Fail(id, "no sval '" + file + "'");
			return;
		}
		if (entry != "")
		{
			@sv = SvalEntry(sv, entry);
			if (sv is null)
			{
				Fail(id, "no entry '" + entry + "' in '" + file + "'");
				return;
			}
		}
		string text = SvalJson(sv, 0);
		uint parts = (text.length() + SVAL_CHUNK - 1) / SVAL_CHUNK;
		if (parts == 0)
			parts = 1;
		for (uint k = 0; k < parts; k++)
		{
			Emit(Reply(id, true).Str("file", args[0]).Int("part", k).Int("of", parts)
				.Str("chunk", text.substr(k * SVAL_CHUNK, SVAL_CHUNK)));
		}
	}
}
