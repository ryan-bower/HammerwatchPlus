"""Transport-realistic identity controls; no native API, launch or profile access."""
import copy
import importlib
import json
import os
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest

SOURCE=Path(os.environ.get("HWP_TOWN_TEST_SOURCE",Path(__file__).resolve().parents[1])).resolve()
sys.path.insert(0,str(SOURCE))
oracle=importlib.import_module("gamelab.bots.qa_town_economy_oracle")
BASE="mainhand_mace_01"
A=.12345679104328156
B=.12345679849386215


def float_node(value):
    stored=struct.unpack("<f",struct.pack("<f",value))[0]
    return {"t":"Float","v":format(stored,".8e")}


def reply(node):
    def count(n,depth=0):
        result,deepest=1,depth
        if n.get("t") in ("Array","Dictionary"):
            for child in n["v"]:
                child=child[1] if n["t"]=="Dictionary" else child
                number,level=count(child,depth+1)
                result+=number;deepest=max(deepest,level)
        return result,deepest
    nodes,depth=count(node)
    return {"ok":True,"schema":"gamelab.itemidentity.v1","complete":True,"truncated":False,
            "slot":"mainhand","base_id":BASE,"nodes":nodes,"depth":depth,"typed":node}


def item(*nodes):
    return reply({"t":"Array","v":list(nodes)})


class TypedTransportControls(unittest.TestCase):
    def test_adjacent_real_f32_values_collapse_in_legacy_transport(self):
        self.assertNotEqual(struct.pack("<f",A),struct.pack("<f",B))
        self.assertEqual(format(A,".6f"),format(B,".6f"))
        old_a={"ok":True,"truncated":False,"value":[{"intensity":float(format(A,".6f"))}]}
        old_b={"ok":True,"truncated":False,"value":[{"intensity":float(format(B,".6f"))}]}
        self.assertEqual(old_a,old_b)
        with self.assertRaises(ValueError):
            oracle.equipment_identity(old_a)

    def test_typed_roundtrip_preserves_adjacent_scalar_f32(self):
        self.assertNotEqual(oracle.equipment_identity(item(float_node(A))),
                            oracle.equipment_identity(item(float_node(B))))

    def test_vectors_use_roundtrip_precision_and_type(self):
        va={"t":"Vector2","v":[float_node(A)["v"],float_node(1)["v"]]}
        vb={"t":"Vector2","v":[float_node(B)["v"],float_node(1)["v"]]}
        self.assertNotEqual(oracle.equipment_identity(item(va)),oracle.equipment_identity(item(vb)))
        with self.assertRaises(ValueError):
            oracle.equipment_identity(item({"t":"Vector2","v":[format(A,".6f"),"1.00000000e+00"]}))

    def test_integer_long_float_and_double_remain_distinct(self):
        cases=({"t":"Integer","v":"1"},{"t":"Long","v":"1"},float_node(1),
               {"t":"Double","v":"1.0000000000000000e+00"})
        identities=[oracle.equipment_identity(item(node)) for node in cases]
        self.assertEqual(len(set(identities)),4)

    def test_subnormal_and_signed_zero_are_not_lost(self):
        smallest=struct.unpack("<f",bytes.fromhex("01000000"))[0]
        self.assertNotEqual(oracle.equipment_identity(item(float_node(smallest))),
                            oracle.equipment_identity(item(float_node(0))))
        self.assertNotEqual(oracle.equipment_identity(item(float_node(-0.0))),
                            oracle.equipment_identity(item(float_node(0.0))))

    def test_string_and_dictionary_key_bytes_are_exact(self):
        raw=b"\x00\x01\n\\\xff"
        encoded=reply({"t":"Dictionary","v":[[raw.hex(),{"t":"String","v":raw.hex()}]]})
        changed=copy.deepcopy(encoded)
        changed["typed"]["v"][0][1]["v"]=b"??\n\\\xff".hex()
        self.assertNotEqual(oracle.equipment_identity(encoded),oracle.equipment_identity(changed))
        with self.assertRaises(ValueError):
            oracle.equipment_identity(item({"t":"String","v":"__truncated"}))

    def test_recursive_truncation_is_refused_even_with_outer_false(self):
        for payload in ({"t":"__truncated","v":"depth"},{"__truncated":"depth"},
                        {"t":"ByteArray","v":"00"},{"t":"String","v":"","__truncated":True}):
            with self.subTest(payload=payload),self.assertRaises(ValueError):
                oracle.equipment_identity(item(payload))

    def test_explicit_completeness_and_recursion_metadata_required(self):
        good=item(float_node(A))
        for changes in ({"complete":False},{"truncated":True},{"nodes":0},{"depth":0},
                        {"base_id":"another_item"},{"schema":"inspect"},{"nodes":True}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                oracle.equipment_identity(dict(good,**changes))

    def test_depth_cap_is_recursive(self):
        node=float_node(A)
        for _ in range(17):
            node={"t":"Array","v":[node]}
        with self.assertRaises(ValueError):
            oracle.equipment_identity(reply(node))

    def test_child_node_and_text_caps_are_not_partial_successes(self):
        cases=(
            {"t":"Array","v":[float_node(A) for _ in range(129)]},
            {"t":"Array","v":[{"t":"Array","v":[float_node(A) for _ in range(4)]} for _ in range(128)]},
            {"t":"Array","v":[{"t":"String","v":"ab"*1024} for _ in range(8)]})
        for node in cases:
            with self.subTest(size=len(node["v"])),self.assertRaises(ValueError):
                oracle.equipment_identity(reply(node))

    def test_dictionary_duplicate_bytes_are_refused_and_order_is_canonical(self):
        node={"t":"Dictionary","v":[["61",float_node(A)],["62",float_node(B)]]}
        first=oracle.equipment_identity(reply(node))
        node["v"].reverse()
        self.assertEqual(first,oracle.equipment_identity(reply(node)))
        node["v"][0][0]=node["v"][1][0]
        with self.assertRaises(ValueError):
            oracle.equipment_identity(reply(node))

    def test_invalid_float_precision_and_nonfinite_are_refused(self):
        for text in ("0.123457","1.234568e-01","nan","inf","1.00000000e+99"):
            with self.subTest(text=text),self.assertRaises(ValueError):
                oracle.equipment_identity(item({"t":"Float","v":text}))

    def test_no_aliasing_after_complete_typed_snapshot(self):
        frame=item(float_node(A))
        before=oracle.equipment_identity(frame)
        frame["typed"]["v"][0]["v"]=float_node(B)["v"]
        self.assertNotEqual(before,oracle.equipment_identity(frame))


class NativeCaseTransportRouting(unittest.TestCase):
    def run_case(self,corrupt):
        module=importlib.import_module("gamelab.bots.qa_gambler_disabled_window")
        previous_checks,previous_time=module.Checks,module.time
        self.addCleanup(setattr,module,"Checks",previous_checks)
        self.addCleanup(setattr,module,"time",previous_time)
        calls=[]
        class Fake(previous_checks):
            def __init__(self,p):
                self.out,self.notes={},[]
                self.balance,self.changed,self.window=0,False,""
                self.g=SimpleNamespace(console=lambda *a:None)
            def set_gold(self,n): self.balance=n
            def gold(self): return self.balance
            def hwp(self,line,*a,**kw):
                if line=="set gambler.enabled 0":self.changed=corrupt;self.window=""
                return "gambler.enabled = 0"
            def gl(self,verb,*args,**kw):
                calls.append((verb,args))
                raw=B if self.changed else A
                if verb in ("equip","kit"):return {"ok":True}
                if verb=="bagitems":return {"main":{"id":BASE,"quality":4,"ilvl":1}}
                if verb=="use":self.window="HWPGamblerMenu";return {"ok":True}
                if verb=="state":return {"window":self.window}
                if verb=="inspect" and args==("player","hwp"):
                    return {"ok":True,"truncated":False,"value":{"bet_tokens":3}}
                if verb=="inspect" and args==("player","equipped"):
                    # Actual legacy precision path: adjacent native values become identical JSON.
                    return {"ok":True,"truncated":False,"value":[{"intensity":float(format(raw,".6f"))}]}
                if verb=="qa_item_identity":return item(float_node(raw))
                if verb=="unitsof":return {args[0]:{"units":[{"unit":1}]}}
                if verb=="press":self.balance-=2000;return {"ok":True}
                raise AssertionError((verb,args))
        module.Checks=Fake
        module.time=SimpleNamespace(sleep=lambda *a:None)
        return module.run(None),calls

    def test_complete_identity_clean_control(self):
        outcome,calls=self.run_case(False)
        self.assertIs(outcome["ok"],True,outcome)
        self.assertEqual(sum(verb=="qa_item_identity" for verb,args in calls),2)
        self.assertNotIn(("inspect",("player","equipped")),calls)

    def test_adjacent_native_change_cannot_hide_behind_rounded_inspect(self):
        outcome,calls=self.run_case(True)
        self.assertIs(outcome["disabled_no_gold_or_item_change"],False,outcome)
        self.assertIs(outcome["ok"],False)
        self.assertNotIn(("inspect",("player","equipped")),calls)


if __name__=="__main__":
    unittest.main(verbosity=2)
