"""Pure driver orchestration controls; stub codec assessment, never native AS.

The bounded setup model uses actual E011 equip rare/ilvl1 -> quality2 and the
existing exact-base kit contract -> requested Rare4 before native Finalize.
HWP_TOWN_TEST_SOURCE selects an isolated source copy, as the existing15 tests do.
"""
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE=Path(os.environ.get("HWP_TOWN_TEST_SOURCE",Path(__file__).resolve().parents[1])).resolve()
sys.path.insert(0,str(SOURCE))
spec=importlib.util.spec_from_file_location("item_transport_driver_under_test",
                                         SOURCE/"gamelab/bots/qa_item_transport_contract.py")
driver=importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class FixtureModel:
    def __init__(self,kit_quality=None):
        self.kit_quality=kit_quality
        self.operations=[]
        self.calibrations=0
        self.setups=0
        self.reads=0
        self.main=None

    def gl_cmd(self,verb,*args):
        self.operations.append(verb)
        if verb=="state":
            return {"phase":"town","player":{"class":"paladin","level":1,"dead":False}}
        if verb=="qa_item_transport_calibrate":
            self.calibrations+=1
            return {"ok":True,"schema":"gamelab.item-calibration.v1","case":args[0]}
        if verb in ("equip","kit"):
            self.setups+=1
            if verb=="equip":
                base,quality,ilvl=args
            else:
                ilvl,quality,base,*_=args
            if quality!="rare":
                return {"ok":False,"error":"bounded model only permits the authored Rare fixture"}
            # The old request reproduces the actual native fixture boundary. This
            # is not a model of the full generator or a newly claimed mechanism.
            actual=2 if verb=="equip" and ilvl==1 else 4
            if verb=="kit" and self.kit_quality is not None:actual=self.kit_quality
            self.main={"id":base,"quality":actual,"ilvl":ilvl,"upgrade":0}
            return {"ok":True,"quality":actual,"ilvl":ilvl}
        if verb=="bagitems":
            return {"main":dict(self.main) if self.main is not None else {}}
        if verb=="qa_item_identity":
            self.reads+=1
            return {"identity":repr(sorted(self.main.items()))}
        raise AssertionError("unexpected driver operation: "+repr((verb,args)))


class ItemTransportDriverControls(unittest.TestCase):
    def run_model(self,*,kit_quality=None,fail_calibration=False):
        game=FixtureModel(kit_quality)
        def assessment(case,reply):
            if fail_calibration and case==driver.CASES[-1]:
                raise ValueError("scripted codec assessment refusal")
            return {"ok":True}
        # Isolate orchestration. No49-case numeric model, typed item parser, AS
        # encoder or native saved-item claim is supplied by these stubs.
        with patch.object(driver,"assess_case",assessment), \
             patch.object(driver,"assess_saved_item",lambda reply:(reply["identity"],{})), \
             patch.object(driver,"time",SimpleNamespace(sleep=lambda _:None)):
            result=driver.run(SimpleNamespace(game=game))
        return result,game

    def test_strict_fixture_completes_three_read_only_snapshots(self):
        result,game=self.run_model()
        self.assertTrue(result["ok"],
                        "fixture did not complete: quality="+str((game.main or {}).get("quality"))
                        +", identity_reads="+str(game.reads))
        self.assertEqual(game.calibrations,49)
        self.assertEqual(game.setups,1)
        self.assertEqual(game.main,{"id":"mainhand_mace_01","quality":4,"ilvl":1,"upgrade":0})
        self.assertEqual(game.reads,3)
        self.assertEqual(result["real_item_read_count"],3)
        self.assertTrue(result["real_item_stable"])
        last_setup=max(i for i,verb in enumerate(game.operations) if verb in ("equip","kit"))
        self.assertEqual(game.operations[last_setup+1:],
                         ["bagitems"]+["qa_item_identity"]*3+["bagitems"])

    def test_wrong_setup_metadata_keeps_zero_identity_reads(self):
        result,game=self.run_model(kit_quality=2)
        self.assertEqual(game.calibrations,49)
        self.assertEqual(game.setups,1)
        self.assertEqual(game.main["quality"],2)
        self.assertFalse(result["ok"])
        self.assertFalse(result["real_item_fixture"])
        self.assertFalse(result["real_item_stable"])
        self.assertEqual(game.reads,0)
        self.assertEqual(result["real_item_read_count"],0)
        self.assertEqual(game.operations[-1],"bagitems")

    def test_failed_calibration_never_prepares_equipment(self):
        result,game=self.run_model(fail_calibration=True)
        self.assertEqual(game.calibrations,49)
        self.assertFalse(result["ok"])
        self.assertFalse(result["real_item_fixture"])
        self.assertEqual(game.setups,0)
        self.assertEqual(game.reads,0)
        self.assertNotIn("bagitems",game.operations)


if __name__=="__main__":
    unittest.main(verbosity=2)
