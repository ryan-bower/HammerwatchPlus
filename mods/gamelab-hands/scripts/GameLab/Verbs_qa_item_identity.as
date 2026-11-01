// Module-owned exact typed Item::SaveItem transport. Does not call SvalJson/Vec.
// Read-only: no setters, RNG, inventory mutation, refresh, or global serializer changes.
namespace GameLab
{
    const uint QA_ITEM_DEPTH = 16;
    const uint QA_ITEM_NODES = 512;
    const uint QA_ITEM_CHILDREN = 128;
    const uint QA_ITEM_STRING_BYTES = 1024;
    const uint QA_ITEM_TEXT = 11000;

    class QAItemTypedEncoder
    {
        uint nodes = 0, deepest = 0;
        bool truncated = false;
        string reason;

        string Refuse(const string &in why, bool cut = false)
        {
            if (reason.isEmpty()) reason = why;
            truncated = truncated || cut;
            return "";
        }

        string Hex(const string &in value)
        {
            if (value.length() > QA_ITEM_STRING_BYTES)
                return Refuse("string byte cap", true);
            const string digits = "0123456789abcdef";
            string encoded;
            for (uint i = 0; i < value.length(); i++)
            {
                uint8 c = value[i];
                encoded += digits.substr(c >> 4, 1) + digits.substr(c & 15, 1);
            }
            return encoded;
        }

        bool FiniteText(const string &in text, bool single)
        {
            // Admit only the canonical scientific form emitted for finite values.
            // Byte checks do not rely on native nonfinite comparison behavior.
            uint size = text.length();
            uint start = size > 0 && text[0] == 45 ? 1 : 0;
            uint exponent = start + 2 + (single ? 8 : 16);
            if (size != exponent + 4 && size != exponent + 5) return false;
            if (text[start] < 48 || text[start] > 57 || text[start + 1] != 46
                || text[exponent] != 101
                || (text[exponent + 1] != 43 && text[exponent + 1] != 45))
                return false;
            for (uint i = start + 2; i < exponent; i++)
                if (text[i] < 48 || text[i] > 57) return false;
            for (uint i = exponent + 2; i < size; i++)
                if (text[i] < 48 || text[i] > 57) return false;
            return true;
        }

        string Number(double value, bool single)
        {
            // Scientific notation preserves subnormals; fixed decimal precision does not.
            // 9/17 significant digits roundtrip binary32/binary64 respectively.
            string text = formatFloat(value, "e", 0, single ? 8 : 16);
            if (!FiniteText(text, single)) return Refuse("nonfinite numeric item value");
            uint used = 0;
            double read = parseFloat(text, used);
            if (used != text.length() || !FiniteText(formatFloat(read, "e", 0, single ? 8 : 16), single)
                || (single ? double(float(read)) != value : read != value))
                return Refuse("numeric format/parse did not roundtrip");
            return text;
        }

        string FloatVector(const string &in tag, uint size, double x, double y, double z = 0, double w = 0)
        {
            array<double> values = {x, y, z, w};
            array<string> encoded;
            for (uint i = 0; i < size; i++)
                encoded.insertLast(Quote(Number(values[i], true)));
            return ReplyNode(tag, RawArray(encoded));
        }

        string IntVector(const string &in tag, uint size, int x, int y, int z = 0, int w = 0)
        {
            array<int> values = {x, y, z, w};
            array<string> encoded;
            for (uint i = 0; i < size; i++) encoded.insertLast(Quote("" + values[i]));
            return ReplyNode(tag, RawArray(encoded));
        }

        string ReplyNode(const string &in tag, const string &in value)
        {
            Json node;
            string encoded = node.Str("t", tag).Raw("v", value).Close();
            return encoded.length() > QA_ITEM_TEXT ? Refuse("typed text cap", true) : encoded;
        }

        string Value(SValue@ value, uint depth)
        {
            if (!reason.isEmpty()) return "";
            nodes++;
            if (nodes > QA_ITEM_NODES) return Refuse("recursive node cap", true);
            if (depth > QA_ITEM_DEPTH) return Refuse("recursive depth cap", true);
            if (depth > deepest) deepest = depth;
            if (value is null || value.GetType() == SValueType::Null)
                return ReplyNode("Null", "null");
            auto type = value.GetType();
            if (type == SValueType::Boolean)
                return ReplyNode("Boolean", value.GetBoolean() ? "true" : "false");
            if (type == SValueType::Integer)
                return ReplyNode("Integer", Quote("" + value.GetInteger()));
            if (type == SValueType::Long)
                return ReplyNode("Long", Quote("" + value.GetLong()));
            if (type == SValueType::Float)
                return ReplyNode("Float", Quote(Number(double(value.GetFloat()), true)));
            if (type == SValueType::String)
                return ReplyNode("String", Quote(Hex(value.GetString())));
            if (type == SValueType::Array)
            {
                auto children = value.GetArray();
                if (children.length() > QA_ITEM_CHILDREN) return Refuse("array child cap", true);
                array<string> encoded;
                uint size = 0;
                for (uint i = 0; i < children.length(); i++)
                {
                    string child = Value(children[i], depth + 1);
                    if (!reason.isEmpty()) return "";
                    size += child.length() + 1;
                    if (size > QA_ITEM_TEXT) return Refuse("array text cap", true);
                    encoded.insertLast(child);
                }
                return ReplyNode("Array", RawArray(encoded));
            }
            if (type == SValueType::Dictionary)
            {
                auto keys = value.GetDictionaryKeys();
                if (keys.length() > QA_ITEM_CHILDREN) return Refuse("dictionary child cap", true);
                keys.sortAsc();
                array<string> encoded;
                uint size = 0;
                for (uint i = 0; i < keys.length(); i++)
                {
                    string key = Hex(keys[i]);
                    string child = Value(value.GetDictionaryEntry(keys[i]), depth + 1);
                    if (!reason.isEmpty()) return "";
                    string pair = "[" + Quote(key) + "," + child + "]";
                    size += pair.length() + 1;
                    if (size > QA_ITEM_TEXT) return Refuse("dictionary text cap", true);
                    encoded.insertLast(pair);
                }
                return ReplyNode("Dictionary", RawArray(encoded));
            }
            if (type == SValueType::Vector2)
            { vec2 v = value.GetVector2(); return FloatVector("Vector2", 2, v.x, v.y); }
            if (type == SValueType::Vector4)
            { vec4 v = value.GetVector4(); return FloatVector("Vector4", 4, v.x, v.y, v.z, v.w); }
            if (type == SValueType::IVector2)
            { ivec2 v = value.GetIVector2(); return IntVector("IVector2", 2, v.x, v.y); }
            // Match runtime enum names for members not named by all SDK script versions.
            string name = Reflect::TypeOf(type).GetEnumName(int(type));
            if (name == "Double")
                return ReplyNode("Double", Quote(Number(value.GetDouble(), false)));
            if (name == "Vector3")
            { vec3 v = value.GetVector3(); return FloatVector("Vector3", 3, v.x, v.y, v.z); }
            if (name == "IVector3")
            { ivec3 v = value.GetIVector3(); return IntVector("IVector3", 3, v.x, v.y, v.z); }
            if (name == "IVector4")
            { ivec4 v = value.GetIVector4(); return IntVector("IVector4", 4, v.x, v.y, v.z, v.w); }
            return Refuse("unsupported SValue type: " + name);
        }
    }

    void VerbQAItemIdentity(const string &in id, array<string>@ args)
    {
        auto rec = GetLocalPlayerRecord();
        int slot = int(EquippedItemsSlots::MainHand);
        if (args.length() != 1 || args[0].isEmpty() || args[0].length() > 128
            || rec is null || rec.equipped is null || slot < 0
            || slot >= int(rec.equipped.m_items.length()))
        { Fail(id, "usage: qa_item_identity <exact expected mainhand base id>; requires local equipped record"); return; }
        auto item = cast<Equipment::Item>(rec.equipped.m_items[slot]);
        if (item is null || item.baseItem is null || item.baseItem.m_id != args[0])
        { Fail(id, "mainhand item is absent, nongenerated, or has another base id"); return; }
        SValueBuilder builder;
        Item::SaveItem(builder, item);
        SValue@ saved = builder.Build();
        if (saved is null)
        { Fail(id, "Item::SaveItem produced no value"); return; }
        QAItemTypedEncoder encoder;
        string typed = encoder.Value(saved, 0);
        saved.Delete();
        if (!encoder.reason.isEmpty())
        {
            Emit(Reply(id, false).Str("schema", "gamelab.itemidentity.v1")
                .Bool("complete", false).Bool("truncated", encoder.truncated)
                .Str("error", encoder.reason).Int("nodes", encoder.nodes).Int("depth", encoder.deepest));
            return;
        }
        Emit(Reply(id, true).Str("schema", "gamelab.itemidentity.v1")
            .Str("slot", "mainhand").Str("base_id", item.baseItem.m_id)
            .Bool("complete", true).Bool("truncated", false)
            .Int("nodes", encoder.nodes).Int("depth", encoder.deepest).Raw("typed", typed));
    }
}
namespace Modules
{
    class GameLabItemIdentityVerbs : Module
    {
        GameLabItemIdentityVerbs()
        {
            super("gamelab-item-identity-verbs");
            GameLab::RegisterVerb("qa_item_identity", "<exact expected mainhand base id>",
                GameLab::Verb(GameLab::VerbQAItemIdentity));
        }
    }
}

