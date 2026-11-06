"""Draft host negative controls only. Passing these cannot calibrate native AS."""
import copy
import unittest

from gamelab.bots.qa_item_transport_contract_oracle import assess_case, assess_saved_item
from gamelab.bots.qa_item_transport_contract import run
from gamelab.hps import hash_string


def frame(case,tag,text,input_text,nodes=1,depth=0,seed=0):
    return {"ok":True,"schema":"gamelab.item-calibration.v1","case":case,"source_type":tag,
            "input":input_text,"parsed_all":True,"nodes_start":seed,
            "result":{"accepted":True,"complete":True,"truncated":False,"reason":"",
                      "nodes":nodes,"depth":depth,"typed":{"t":tag,"v":text}}}


def saved_item(intensity="1.23456791e-01"):
    base_hash=hash_string("mainhand_mace_01")
    if base_hash >= 1 << 31:base_hash-=1 << 32
    values=[{"t":"Integer","v":str(v)} for v in (4,base_hash,1,0,0,0,123)]
    values.insert(2,{"t":"Float","v":intensity})
    return {"ok":True,"schema":"gamelab.itemidentity.v1","slot":"mainhand",
            "base_id":"mainhand_mace_01","complete":True,"truncated":False,
            "nodes":9,"depth":1,"typed":{"t":"Array","v":values}}


class CalibrationOracleNegatives(unittest.TestCase):
    def test_actual_negative_zero_bits_are_required(self):
        good=frame("f32_negzero","Float","-0.00000000e+00","-0.0")
        self.assertEqual(assess_case("f32_negzero",good)["ieee_little_endian"],"00000080")
        bad=copy.deepcopy(good);bad["result"]["typed"]["v"]="0.00000000e+00"
        with self.assertRaises(ValueError):assess_case("f32_negzero",bad)

    def test_double_negative_zero_is_not_numeric_zero_equality(self):
        good=frame("f64_negzero","Double","-0.0000000000000000e+00","-0.0")
        self.assertEqual(assess_case("f64_negzero",good)["ieee_little_endian"],"0000000000000080")
        good["result"]["typed"]["v"]="0.0000000000000000e+00"
        with self.assertRaises(ValueError):assess_case("f64_negzero",good)

    def test_float_adjacent_values_cannot_collapse(self):
        good=frame("f32_adjacent_a","Float","1.23456791e-01","0.12345679104328156")
        assess_case("f32_adjacent_a",good)
        good["result"]["typed"]["v"]="1.23456798e-01"
        with self.assertRaises(ValueError):assess_case("f32_adjacent_a",good)

    def test_double_precision_cannot_be_silently_cast_to_float(self):
        good=frame("f64_adjacent","Double","1.0000000000000002e+00","1.0000000000000002")
        assess_case("f64_adjacent",good)
        good["result"]["typed"]["v"]="1.0000000000000000e+00"
        with self.assertRaises(ValueError):assess_case("f64_adjacent",good)

    def test_subnormal_cannot_flush_to_zero(self):
        good=frame("f32_subnormal","Float","1.40129846e-45","1.401298464324817e-45")
        self.assertEqual(assess_case("f32_subnormal",good)["ieee_little_endian"],"01000000")
        good["result"]["typed"]["v"]="0.00000000e+00"
        with self.assertRaises(ValueError):assess_case("f32_subnormal",good)

    def test_refusal_has_no_partial_payload(self):
        row={"ok":True,"schema":"gamelab.item-calibration.v1","case":"depth17","source_type":"Array",
             "input":"","parsed_all":True,"nodes_start":0,
             "result":{"accepted":False,"complete":False,"truncated":True,
                       "reason":"recursive depth cap","nodes":18,"depth":16}}
        assess_case("depth17",row)
        row["result"]["typed"]={"t":"Null","v":None}
        with self.assertRaises(ValueError):assess_case("depth17",row)

    def test_nonfinite_requires_correct_native_refusal(self):
        row={"ok":True,"schema":"gamelab.item-calibration.v1","case":"f32_nan","source_type":"Float",
             "input":"nan","parsed_all":True,"nodes_start":0,
             "result":{"accepted":False,"complete":False,"truncated":False,
                       "reason":"nonfinite numeric item value","nodes":1,"depth":0}}
        assess_case("f32_nan",row)
        row["result"]["reason"]="recursive depth cap"
        with self.assertRaises(ValueError):assess_case("f32_nan",row)

    def test_fixture_parse_failure_is_not_encoder_proof(self):
        good=frame("f32_zero","Float","0.00000000e+00","0.0")
        good["parsed_all"]=False
        with self.assertRaises(ValueError):assess_case("f32_zero",good)

    def test_seeded_budget_is_explicit_not_a_natural_tree(self):
        good=frame("seeded_nodes512","Null",None,"",nodes=512,seed=511)
        self.assertTrue(assess_case("seeded_nodes512",good)["seeded_budget"])
        good["nodes_start"]=0
        with self.assertRaises(ValueError):assess_case("seeded_nodes512",good)

    def test_lossy_legacy_item_reply_is_never_fallback(self):
        with self.assertRaises(ValueError):
            assess_saved_item({"ok":True,"truncated":False,"value":[4,1,.123457,1,0,0,0]})

    def test_top_reply_case_schema_and_success_are_bound(self):
        good=frame("f32_zero","Float","0.00000000e+00","0.0")
        assess_case("f32_zero",good)
        for key,value in (("case","f64_zero"),("schema","gamelab.itemidentity.v1"),("ok",False)):
            with self.subTest(field=key):
                bad=copy.deepcopy(good);bad[key]=value
                with self.assertRaises(ValueError):assess_case("f32_zero",bad)

    def test_accepted_reply_must_be_complete_and_untruncated(self):
        good=frame("f32_zero","Float","0.00000000e+00","0.0")
        for key,value in (("complete",False),("truncated",True),("reason","recursive depth cap")):
            with self.subTest(field=key):
                bad=copy.deepcopy(good);bad["result"][key]=value
                with self.assertRaises(ValueError):assess_case("f32_zero",bad)

    def test_unsupported_refusal_is_native_type_specific(self):
        row={"ok":True,"schema":"gamelab.item-calibration.v1","case":"unsupported_bytes",
             "source_type":"ByteArray","input":"","parsed_all":True,"nodes_start":0,
             "result":{"accepted":False,"complete":False,"truncated":False,
                       "reason":"unsupported SValue type: ByteArray","nodes":1,"depth":0}}
        assess_case("unsupported_bytes",row)
        row["source_type"]="String"
        with self.assertRaises(ValueError):assess_case("unsupported_bytes",row)

    def test_unsupported_typed_success_cannot_use_a_sentinel(self):
        good=frame("null","Null",None,"")
        good["source_type"]="ByteArray";good["result"]["typed"]={"t":"ByteArray","v":"000102ff"}
        with self.assertRaises(ValueError):assess_case("null",good)

    def test_real_saved_item_positive_and_adjacent_float_identity(self):
        a,summary=assess_saved_item(saved_item())
        b,_=assess_saved_item(saved_item("1.23456798e-01"))
        self.assertEqual(summary["modifiers"],1)
        self.assertNotEqual(a,b)

    def test_real_saved_item_positive_and_negative_zero_identity(self):
        a,_=assess_saved_item(saved_item("0.00000000e+00"))
        b,_=assess_saved_item(saved_item("-0.00000000e+00"))
        self.assertNotEqual(a,b)

    def test_real_saved_item_shape_and_required_field_types(self):
        good=saved_item()
        for index,replacement in ((0,{"t":"Integer","v":"3"}),
                                  (1,{"t":"Integer","v":"0"}),
                                  (2,{"t":"Double","v":"1.2345679104328156e-01"}),
                                  (3,{"t":"Integer","v":"2"}),
                                  (7,{"t":"String","v":"313233"})):
            with self.subTest(index=index):
                bad=copy.deepcopy(good);bad["typed"]["v"][index]=replacement
                with self.assertRaises(ValueError):assess_saved_item(bad)

    def test_real_saved_item_exact_frame_and_completeness(self):
        good=saved_item()
        for key,value in (("slot","offhand"),("base_id","mainhand_sword_01"),
                          ("truncated",True),("complete",False),("nodes",8),("depth",2)):
            with self.subTest(field=key):
                bad=copy.deepcopy(good);bad[key]=value
                with self.assertRaises(ValueError):assess_saved_item(bad)

    def test_real_saved_item_short_array_is_refused(self):
        bad=saved_item();bad["typed"]["v"]=bad["typed"]["v"][:6];bad["nodes"]=7
        with self.assertRaises(ValueError):assess_saved_item(bad)

    def test_bot_wrong_case_reply_stops_without_fixture_mutation(self):
        class Game:
            def __init__(self):self.calls=[]
            def gl_cmd(self,*args):
                self.calls.append(args)
                if args==("state",):
                    return {"phase":"town","player":{"class":"paladin","level":1,"dead":False}}
                if args==("qa_item_transport_calibrate","f32_zero"):
                    return frame("f64_zero","Double","0.0000000000000000e+00","0.0")
                raise AssertionError("unexpected command after prerequisite refusal: "+repr(args))
        class Pilot:pass
        p=Pilot();p.game=Game()
        result=run(p)
        self.assertFalse(result["ok"])
        self.assertEqual(result["observed_case_count"],1)
        self.assertEqual(result["real_item_read_count"],0)
        self.assertEqual(p.game.calls,[("state",),("qa_item_transport_calibrate","f32_zero")])

    def test_bot_bad_player_fixture_stops_without_diagnostic(self):
        class Game:
            def __init__(self):self.calls=[]
            def gl_cmd(self,*args):
                self.calls.append(args)
                return {"phase":"town","player":{"class":"ranger","level":1,"dead":False}}
        class Pilot:pass
        p=Pilot();p.game=Game()
        result=run(p)
        self.assertFalse(result["ok"])
        self.assertEqual(result["observed_case_count"],0)
        self.assertEqual(p.game.calls,[("state",)])


if __name__=="__main__":
    unittest.main(verbosity=2)
