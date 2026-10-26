// Dev Arena: copy-on-write patches of a skill's level params.
//
// A PlayerSkillDef keeps one SValue per level (m_levelParams[0] = the "skill" dict,
// [k] = upgrades[k-1], PlayerClass.as:94-110). Resource SValues are shared and cached at
// boot, so a patch never edits one in place: it builds a copy with one leaf replaced and
// swaps the copy into m_levelParams[k]. The next PlayerBase.LoadSkills rebuilds the live
// skill from it (PlayerBase.as:165-260), keeping cooldowns through Save/Load.
//
// A path is dot-separated: dictionary keys and array indices ("cooldown",
// "binds.area-dmg", "timeline.2", "blocking").
namespace HWP
{
namespace DevArena
{
	string TypeName(SValueType t)
	{
		if (t == SValueType::Integer) return "int";
		if (t == SValueType::Float) return "float";
		if (t == SValueType::Boolean) return "bool";
		if (t == SValueType::String) return "string";
		if (t == SValueType::Dictionary) return "dict";
		if (t == SValueType::Array) return "array";
		if (t == SValueType::IVector2) return "ivec2";
		if (t == SValueType::Vector2) return "vec2";
		return "other";
	}

	// a leaf as text, the inverse of PushLeaf; "" for containers
	string LeafText(SValue@ v)
	{
		if (v is null)
			return "";
		auto t = v.GetType();
		if (t == SValueType::Integer) return "" + v.GetInteger();
		if (t == SValueType::Float) return formatFloat(v.GetFloat(), "", 0, 3);
		if (t == SValueType::Boolean) return v.GetBoolean() ? "true" : "false";
		if (t == SValueType::String) return v.GetString();
		if (t == SValueType::IVector2) { auto i = v.GetIVector2(); return i.x + "," + i.y; }
		if (t == SValueType::Vector2) { auto f = v.GetVector2(); return formatFloat(f.x, "", 0, 3) + "," + formatFloat(f.y, "", 0, 3); }
		return "";
	}

	bool IsIntText(const string &in s)
	{
		if (s.length() == 0)
			return false;
		for (uint i = 0; i < s.length(); i++)
		{
			uint8 c = s[i];
			if (c == 45 && i == 0 && s.length() > 1) // '-'
				continue;
			if (c < 48 || c > 57)
				return false;
		}
		return true;
	}

	// IsIntText and inside int32: 4294967396 is digits but would land as 100
	bool InInt32(const string &in s)
	{
		bool neg = s[0] == 45;
		uint i = neg ? 1 : 0;
		while (i + 1 < s.length() && s[i] == 48)
			i++;
		string d = s.substr(i);
		if (d.length() != 10)
			return d.length() < 10;
		return d <= (neg ? "2147483648" : "2147483647");
	}

	bool IsNumText(const string &in s)
	{
		if (IsIntText(s))
			return true;
		auto parts = s.split(".");
		return parts.length() == 2 && (parts[0].length() == 0 || parts[0] == "-" || IsIntText(parts[0])) && IsIntText(parts[1]) && parts[1][0] != 45;
	}

	// push `value` as type t (the type of the leaf it replaces); a new key infers int, float,
	// bool, then string
	bool PushLeaf(SValueBuilder& b, const string &in name, bool named, SValueType t, bool isNew, const string &in value, string &out err)
	{
		if (isNew)
		{
			if (IsIntText(value)) t = SValueType::Integer;
			else if (IsNumText(value)) t = SValueType::Float;
			else if (value == "true" || value == "false") t = SValueType::Boolean;
			else t = SValueType::String;
		}

		if (t == SValueType::Integer)
		{
			if (!IsIntText(value)) { err = "'" + value + "' is not an int"; return false; }
			if (!InInt32(value)) { err = "'" + value + "' is out of int range"; return false; }
			if (named) b.PushInteger(name, parseInt(value)); else b.PushInteger(parseInt(value));
		}
		else if (t == SValueType::Float)
		{
			if (!IsNumText(value)) { err = "'" + value + "' is not a number"; return false; }
			if (named) b.PushFloat(name, parseFloat(value)); else b.PushFloat(parseFloat(value));
		}
		else if (t == SValueType::Boolean)
		{
			if (value != "true" && value != "false") { err = "'" + value + "' is not true/false"; return false; }
			if (named) b.PushBoolean(name, value == "true"); else b.PushBoolean(value == "true");
		}
		else if (t == SValueType::String)
		{
			if (named) b.PushString(name, value); else b.PushString(value);
		}
		else if (t == SValueType::IVector2)
		{
			auto parts = value.split(",");
			if (parts.length() != 2 || !IsIntText(parts[0]) || !IsIntText(parts[1])) { err = "'" + value + "' is not x,y"; return false; }
			if (!InInt32(parts[0]) || !InInt32(parts[1])) { err = "'" + value + "' is out of int range"; return false; }
			ivec2 iv(parseInt(parts[0]), parseInt(parts[1]));
			if (named) b.PushIVector2(name, iv); else b.PushIVector2(iv);
		}
		else
		{
			err = "cannot set a " + TypeName(t) + " leaf";
			return false;
		}
		return true;
	}

	// write v under name into b; the node on the path gets descended, its leaf replaced
	// a key that is not there yet: nested dicts down to the leaf (an upgrade with no "binds")
	bool PushNew(SValueBuilder& b, const array<string>@ path, uint depth, const string &in value, SValueType hint, string &out err)
	{
		if (depth + 1 == path.length())
			return PushLeaf(b, path[depth], true, hint, hint == SValueType::Null, value, err);
		if (IsIntText(path[depth + 1]))
		{
			err = "no array '" + path[depth] + "' to index";
			return false;
		}
		b.PushDictionary(path[depth]);
		if (!PushNew(b, path, depth + 1, value, hint, err))
			return false;
		b.PopDictionary();
		return true;
	}

	bool WriteNode(SValueBuilder& b, const string &in name, bool named, SValue@ v, bool live,
		const array<string>@ path, uint depth, const string &in value, string &out err, SValueType hint)
	{
		if (live && depth == path.length())
			return PushLeaf(b, name, named, v.GetType(), false, value, err);

		auto t = v.GetType();
		if (!live || (t != SValueType::Dictionary && t != SValueType::Array))
		{
			if (live)
			{
				err = "'" + path[depth - 1] + "' is a " + TypeName(t) + ", not a container";
				return false;
			}
			if (named) b.PushSimple(name, v.Copy()); else b.PushSimple(v.Copy());
			return true;
		}

		if (t == SValueType::Dictionary)
		{
			if (named) b.PushDictionary(name); else b.PushDictionary();
			auto keys = v.GetDictionaryKeys();
			bool found = false;
			for (uint i = 0; i < keys.length(); i++)
			{
				bool hit = keys[i] == path[depth];
				found = found || hit;
				if (!WriteNode(b, keys[i], true, v.GetDictionaryEntry(keys[i]), hit, path, depth + 1, value, err, hint))
					return false;
			}
			if (!found && !PushNew(b, path, depth, value, hint, err))
				return false;
			b.PopDictionary();
			return true;
		}

		auto arr = v.GetArray();
		if (!IsIntText(path[depth]) || parseInt(path[depth]) < 0 || uint(parseInt(path[depth])) >= arr.length())
		{
			err = "index '" + path[depth] + "' out of range (" + arr.length() + ")";
			return false;
		}
		uint idx = uint(parseInt(path[depth]));
		if (named) b.PushArray(name); else b.PushArray();
		for (uint i = 0; i < arr.length(); i++)
			if (!WriteNode(b, "", false, arr[i], i == idx, path, depth + 1, value, err, hint))
				return false;
		b.PopArray();
		return true;
	}

	// a copy of root (a dictionary) with the leaf at path set to value; null and err on failure.
	// A key that is missing is added; it takes the type `hint` (the base level's leaf type),
	// or, without a hint, the type the text reads as (int, float, bool, string).
	SValue@ PatchCopy(SValue@ root, const string &in path, const string &in value, string &out err,
		SValueType hint = SValueType::Null)
	{
		if (root is null || root.GetType() != SValueType::Dictionary)
		{
			err = "root is not a dictionary";
			return null;
		}
		auto parts = path.split(".");
		if (path.length() == 0 || parts.length() == 0)
		{
			err = "empty path";
			return null;
		}
		SValueBuilder b;
		if (!WriteNode(b, "", false, root, true, parts, 0, value, err, hint))
			return null;
		return b.Build();
	}

	// the leaf at path, or null
	SValue@ Lookup(SValue@ root, const string &in path)
	{
		auto parts = path.split(".");
		SValue@ v = root;
		for (uint i = 0; v !is null && i < parts.length(); i++)
		{
			auto t = v.GetType();
			if (t == SValueType::Dictionary)
				@v = v.GetDictionaryEntry(parts[i]);
			else if (t == SValueType::Array && IsIntText(parts[i]))
			{
				auto arr = v.GetArray();
				int idx = parseInt(parts[i]);
				@v = (idx >= 0 && uint(idx) < arr.length()) ? arr[idx] : null;
			}
			else
				@v = null;
		}
		return v;
	}
}
}
