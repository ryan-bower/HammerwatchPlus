"""Independent fixed calibration expectations. Parses actual native replies; no game I/O."""
import json
import math
import re
import struct

from gamelab.hps import hash_string
from gamelab.bots.qa_town_economy_oracle import equipment_identity

BASE_ITEM = "mainhand_mace_01"
F32 = {
 "f32_zero":"0.0", "f32_negzero":"-0.0", "f32_subnormal":"1.401298464324817e-45",
 "f32_min_normal":"1.1754943508222875e-38", "f32_max":"3.4028234663852886e38",
 "f32_negmax":"-3.4028234663852886e38", "f32_repr":"0.1",
 "f32_adjacent_a":"0.12345679104328156", "f32_adjacent_b":"0.12345679849386215",
 "f32_nan":"nan", "f32_inf":"inf"}
F64 = {
 "f64_zero":"0.0", "f64_negzero":"-0.0", "f64_subnormal":"4.9406564584124654e-324",
 "f64_min_normal":"2.2250738585072014e-308", "f64_max":"1.7976931348623157e308",
 "f64_negmax":"-1.7976931348623157e308", "f64_repr":"0.1",
 "f64_adjacent":"1.0000000000000002", "f64_nan":"nan", "f64_inf":"inf", "f64_neginf":"-inf"}
OTHER_CASES = ("null","true","false","i32_min","i32_max","i64_min","i64_max",
 "vec2","vec3","vec4","ivec2","ivec3","ivec4","byte_string_key","depth16","depth17",
 "array128","array129","dict128","dict129","string1024","string1025","text5","text6",
 "seeded_nodes512","seeded_nodes513","unsupported_bytes")
CASES = tuple(F32) + tuple(F64) + OTHER_CASES
REFUSALS = {
 "depth17":("recursive depth cap",True,18,16),
 "array129":("array child cap",True,1,0),
 "dict129":("dictionary child cap",True,1,0),
 "string1025":("string byte cap",True,1,0),
 "text6":("array text cap",True,7,1),
 "seeded_nodes513":("recursive node cap",True,513,0),
 "unsupported_bytes":("unsupported SValue type: ByteArray",False,1,0)}
for _case, _token in tuple(F32.items()) + tuple(F64.items()):
    if _token in ("nan","inf","-inf"):
        REFUSALS[_case] = ("nonfinite numeric item value",False,1,0)


def bits(value, single):
    return struct.pack("<f" if single else "<d", float(value)).hex()


def number(value, single):
    return ("Float" if single else "Double", bits(value,single))


def expected(case):
    if case in F32: return number(F32[case],True)
    if case in F64: return number(F64[case],False)
    if case == "null" or case.startswith("seeded_nodes"): return ("Null",None)
    if case in ("true","false"): return ("Boolean",case=="true")
    if case.startswith("i32_"): return ("Integer",str(-(1<<31) if case.endswith("min") else (1<<31)-1))
    if case.startswith("i64_"): return ("Long",str(-(1<<63) if case.endswith("min") else (1<<63)-1))
    if case == "vec2": return ("Vector2",(bits(F32["f32_adjacent_a"],True),bits("-0.0",True)))
    if case == "vec3": return ("Vector3",(bits(F32["f32_subnormal"],True),bits(F32["f32_adjacent_b"],True),bits("-1",True)))
    if case == "vec4": return ("Vector4",tuple(bits(x,True) for x in (F32["f32_max"],F32["f32_min_normal"],"0","-0.0")))
    if case == "ivec2": return ("IVector2",("-2147483648","2147483647"))
    if case == "ivec3": return ("IVector3",("-1","0","1"))
    if case == "ivec4": return ("IVector4",("-2147483648","-1","1","2147483647"))
    if case == "byte_string_key": return ("Dictionary",(("00010a5cff",("String","00010a5cff")),))
    if case == "depth16":
        node=("Null",None)
        for _ in range(16): node=("Array",(node,))
        return node
    if case == "array128": return ("Array",tuple(("Null",None) for _ in range(128)))
    if case == "dict128":
        return ("Dictionary",tuple(sorted((("k"+str(i)).encode().hex(),("Null",None)) for i in range(128))))
    if case == "string1024": return ("String","41"*1024)
    if case == "text5": return ("Array",tuple(("String","41"*1024) for _ in range(5)))
    raise ValueError("not an accepted calibration case")


def normalize(node):
    """Validate typed data and return kind plus IEEE bytes, not decimal-value equality."""
    count,deepest=0,0
    def hex_value(value):
        if type(value) is not str or len(value)>2048 or len(value)%2 or re.fullmatch("[0-9a-f]*",value) is None:
            raise ValueError("invalid bytehex")
        return value
    def int_value(value,width):
        if type(value) is not str or re.fullmatch(r"-?(0|[1-9][0-9]*)",value) is None:
            raise ValueError("invalid decimal integer")
        integer=int(value)
        if not -(1<<(width-1))<=integer<(1<<(width-1)) or str(integer)!=value:
            raise ValueError("integer width/canonical mismatch")
        return value
    def fp_value(value,single):
        decimals=8 if single else 16
        if type(value) is not str or re.fullmatch(r"-?[0-9]\.\d{"+str(decimals)+r"}e[+-]\d{2,3}",value) is None:
            raise ValueError("missing roundtrip precision/scientific text")
        parsed=float(value)
        if not math.isfinite(parsed): raise ValueError("unexpected nonfinite accepted payload")
        encoded=struct.pack("<f" if single else "<d",parsed)
        restored=struct.unpack("<f" if single else "<d",encoded)[0]
        # A syntactically padded rounded/underflowed value is not canonical source output.
        if format(restored,"."+str(decimals)+"e") != value:
            raise ValueError("numeric payload does not roundtrip canonically")
        return encoded.hex()
    def walk(value,depth):
        nonlocal count,deepest
        count+=1;deepest=max(deepest,depth)
        if depth>16 or count>512 or not isinstance(value,dict) or set(value)!={"t","v"}:
            raise ValueError("recursive typed structure refused")
        tag,data=value["t"],value["v"]
        if tag=="Null" and data is None:return(tag,None)
        if tag=="Boolean" and type(data) is bool:return(tag,data)
        if tag in ("Integer","Long"):return(tag,int_value(data,32 if tag=="Integer" else 64))
        if tag in ("Float","Double"):return(tag,fp_value(data,tag=="Float"))
        if tag=="String":return(tag,hex_value(data))
        if tag in ("Vector2","Vector3","Vector4","IVector2","IVector3","IVector4"):
            if not isinstance(data,list) or len(data)!=int(tag[-1]):raise ValueError("vector width mismatch")
            return(tag,tuple(int_value(x,32) if tag.startswith("I") else fp_value(x,True) for x in data))
        if tag in ("Array","Dictionary") and isinstance(data,list) and len(data)<=128:
            if tag=="Array":return(tag,tuple(walk(x,depth+1) for x in data))
            pairs=[];keys=set()
            for pair in data:
                if not isinstance(pair,list) or len(pair)!=2:raise ValueError("dictionary pair malformed")
                key=hex_value(pair[0])
                if key in keys:raise ValueError("dictionary key duplicate")
                keys.add(key);pairs.append((key,walk(pair[1],depth+1)))
            return(tag,tuple(sorted(pairs)))
        raise ValueError("unsupported typed content")
    normalized=walk(node,0)
    if len(json.dumps(node,separators=(",",":"),allow_nan=False))>11000:
        raise ValueError("typed text exceeds limit")
    return normalized,count,deepest


def assess_case(case,reply):
    if case not in CASES:raise ValueError("unknown expected case")
    if not isinstance(reply,dict) or reply.get("ok") is not True or reply.get("schema")!="gamelab.item-calibration.v1" or reply.get("case")!=case:
        raise ValueError("diagnostic reply identity failed")
    token=F32.get(case,F64.get(case,""))
    if case in ("i64_min","i64_max"):token="-9223372036854775808" if case.endswith("min") else "9223372036854775807"
    seed=511 if case=="seeded_nodes512" else 512 if case=="seeded_nodes513" else 0
    if reply.get("parsed_all") is not True or reply.get("input")!=token or type(reply.get("nodes_start")) is not int or reply["nodes_start"]!=seed:
        raise ValueError("fixture construction/parse/seed metadata mismatch")
    result=reply.get("result")
    if not isinstance(result,dict):raise ValueError("missing encoder result")
    if case in REFUSALS:
        reason,truncated,nodes,depth=REFUSALS[case]
        source_type=("Float" if case in F32 else "Double" if case in F64 else
                     "Dictionary" if case=="dict129" else "String" if case=="string1025" else
                     "Null" if case=="seeded_nodes513" else "ByteArray" if case=="unsupported_bytes" else "Array")
        if (reply.get("source_type")!=source_type or result.get("accepted") is not False
            or result.get("complete") is not False or result.get("truncated") is not truncated
            or result.get("reason")!=reason or "typed" in result or "payload" in result
            or type(result.get("nodes")) is not int or result["nodes"]!=nodes
            or type(result.get("depth")) is not int or result["depth"]!=depth):
            raise ValueError("refusal wrong/partial/unrelated reason")
        return {"case":case,"ok":True,"refused":reason,"seeded_budget":bool(seed)}
    normalized,nodes,depth=normalize(result.get("typed"))
    if (reply.get("source_type")!=normalized[0] or result.get("accepted") is not True
        or result.get("complete") is not True or result.get("truncated") is not False
        or result.get("reason")!="" or type(result.get("nodes")) is not int
        or result["nodes"]!=nodes+seed or type(result.get("depth")) is not int or result["depth"]!=depth
        or normalized!=expected(case)):
        raise ValueError("native typed value/bits/type/completeness mismatch")
    summary={"case":case,"ok":True,"source_type":normalized[0],"nodes":nodes,"seeded_budget":bool(seed)}
    if normalized[0] in ("Float","Double"):summary["ieee_little_endian"]=normalized[1]
    if normalized[0] in ("Vector2","Vector3","Vector4"):summary["ieee_little_endian"]=list(normalized[1])
    return summary


def assess_saved_item(reply):
    canonical=equipment_identity(reply,BASE_ITEM)
    normalized,nodes,depth=normalize(reply["typed"])
    values=normalized[1]
    base_hash=hash_string(BASE_ITEM)
    if base_hash>=(1<<31):base_hash-=1<<32
    if (normalized[0]!="Array" or len(values)<7
        or any(values[i][0]!="Integer" for i in (0,1,3,4,5,6))
        or values[0][1]!="4" or values[1][1]!=str(base_hash) or values[2][0]!="Float"
        or values[3][1]!="1" or values[4][1]!="0"
        or any(value[0]!="Integer" for value in values[7:])):
        raise ValueError("real generated-item save shape/base/quality/level mismatch")
    return canonical,{"intensity_ieee_little_endian":values[2][1],"nodes":nodes,"depth":depth,"modifiers":len(values)-7}

