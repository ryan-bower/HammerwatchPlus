"""UNRUN draft controls for nullable original vs stable straight-pose model cache.

Pure fakes model the current native PlayerVisuals.GetModel null-cache behavior.
They do not execute AngelScript or establish the actual E009 saved-baseline value.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
PLAYER_MATERIAL=object()


class Wrapper:
    def __init__(self,resource,material=PLAYER_MATERIAL):
        self.resource=resource;self.material=material


class Item:
    def __init__(self,resource,original=None):
        self.resource=resource;self.tmp=original


class NativeVisuals:
    """CreateCharacterCustomize.as475-485: wrapper identity is a lazy cache."""
    def __init__(self):self.constructed=[]
    def construct(self,resource):
        result=Wrapper(resource);self.constructed.append(result);return result
    def get_model(self,item):
        if item is None or item.resource is None:return None
        if item.tmp is not None:return item.tmp
        item.tmp=self.construct(item.resource)
        return item.tmp


class Hand:
    def __init__(self,visuals,legacy=False):
        self.visuals=visuals;self.legacy=legacy;self.item=None;self.original=None;self.straight=None
        self.restores=[]
    def clear(self):
        if self.item is not None:
            self.item.tmp=self.original
            self.restores.append((self.item,self.original))
        self.item=None;self.straight=None
    def apply(self,item,pose_model=None,held=False,gun=True):
        # Actual PosedPlayer.Apply returns before either hand while HeldGunOn.
        if held:return False
        if self.item is not None and self.item is not item:
            self.clear();self.original=None
        if item is None or not gun:return False
        if self.item is None:
            self.item=item;self.original=item.tmp;self.straight=self.original
            if not self.legacy and self.straight is None and item.resource is not None:
                self.straight=self.visuals.construct(item.resource)
        wanted=pose_model if pose_model is not None else self.original if self.legacy else self.straight
        changed=item.tmp is not wanted
        item.tmp=wanted
        return changed


class PoseModelCacheTests(unittest.TestCase):
    def test_control_nullable_original_can_reproduce_wrapper_churn_without_resource_change(self):
        visuals=NativeVisuals();item=Item("rifle-base");hand=Hand(visuals,legacy=True)
        handles=[]
        for _ in range(5):
            hand.apply(item);handles.append(visuals.get_model(item))
        self.assertEqual(len(set(handles)),5)
        self.assertTrue(all(value.resource=="rifle-base" for value in handles))
        self.assertIsNone(hand.original)

    def test_null_original_gets_one_stable_renderer_equivalent_base_per_binding(self):
        visuals=NativeVisuals();item=Item("rifle-base");hand=Hand(visuals)
        handles=[];changed=[]
        for _ in range(100):
            changed.append(hand.apply(item));handles.append(visuals.get_model(item))
        self.assertEqual(len(set(handles)),1);self.assertEqual(len(visuals.constructed),1)
        self.assertEqual(changed,[True]+[False]*99)
        self.assertIsNone(hand.original)
        self.assertEqual(handles[0].resource,item.resource);self.assertIs(handles[0].material,PLAYER_MATERIAL)

    def test_existing_nonnull_original_is_reused_exactly_and_never_constructed_over(self):
        original=Wrapper("external-custom");item=Item("rifle-base",original)
        visuals=NativeVisuals();hand=Hand(visuals)
        hand.apply(item);self.assertIs(item.tmp,original)
        hand.apply(item,Wrapper("pose-down"));hand.apply(item)
        self.assertIs(item.tmp,original);self.assertIs(hand.original,original)
        self.assertEqual(visuals.constructed,[])
        hand.clear();self.assertIs(item.tmp,original)

    def test_pose_changes_reuse_straight_cache_but_clear_restores_original_null(self):
        visuals=NativeVisuals();item=Item("rifle-base");hand=Hand(visuals)
        hand.apply(item,Wrapper("pose-down"));straight=hand.straight
        for pose in (None,Wrapper("pose-up"),None,Wrapper("pose-high"),None):
            hand.apply(item,pose)
            if pose is None:self.assertIs(item.tmp,straight)
        self.assertEqual(len(visuals.constructed),1)
        hand.clear()
        self.assertIsNone(item.tmp);self.assertIs(hand.restores[-1][1],None)
        self.assertIsNone(hand.item);self.assertIsNone(hand.straight)
        # The ordinary renderer may subsequently fill that original null again.
        rebuilt=visuals.get_model(item)
        self.assertEqual(rebuilt.resource,"rifle-base");self.assertIsNot(rebuilt,straight)

    def test_replacement_restores_old_item_even_in_bag_then_binds_new_original(self):
        visuals=NativeVisuals();old=Item("rifle-base");new_original=Wrapper("pistol-custom")
        new=Item("pistol-base",new_original);hand=Hand(visuals)
        hand.apply(old,Wrapper("rifle-down"));old_straight=hand.straight
        hand.apply(new,Wrapper("pistol-up"))
        self.assertIsNone(old.tmp);self.assertIs(hand.original,new_original)
        self.assertIs(hand.straight,new_original);self.assertIsNot(hand.straight,old_straight)
        hand.clear();self.assertIs(new.tmp,new_original)

    def test_held_owner_prevents_binding_construction_or_overwrite(self):
        visuals=NativeVisuals();item=Item("rifle-base",Wrapper("held-launcher"));hand=Hand(visuals)
        held=item.tmp
        self.assertFalse(hand.apply(item,Wrapper("pose-down"),held=True))
        self.assertIs(item.tmp,held);self.assertIsNone(hand.item);self.assertEqual(visuals.constructed,[])
        hand.apply(item,held=False);baseline=hand.straight
        item.tmp=Wrapper("another-held");held=item.tmp
        self.assertFalse(hand.apply(item,held=True));self.assertIs(item.tmp,held)
        item.tmp=baseline;hand.apply(item);self.assertIs(item.tmp,baseline)

    def test_held_entry_exit_and_swap_keep_original_separate_from_held_restore(self):
        visuals=NativeVisuals();old=Item("rifle-base");new_original=Wrapper("new-original")
        new=Item("pistol-base",new_original);hand=Hand(visuals);posed=Wrapper("rifle-down")
        hand.apply(old,posed);original_straight=hand.straight
        held_was=old.tmp;old.tmp=Wrapper("held-rpg");held=old.tmp
        hand.apply(new,held=True)
        self.assertIs(old.tmp,held);self.assertIs(hand.item,old)
        self.assertIsNone(hand.original);self.assertIs(hand.straight,original_straight)
        # HeldModel.RestoreHeld restores the exact item/model it saved at entry.
        old.tmp=held_was;hand.apply(new,held=False)
        self.assertIsNone(old.tmp);self.assertIs(hand.original,new_original)
        self.assertIs(new.tmp,new_original);self.assertEqual(len(visuals.constructed),1)

    def test_local_and_husk_shared_visuals_keep_native_resource_and_player_material(self):
        # Source provenance: Player and PlayerHusk -> PlayerBase, PlayerVisuals.
        # This models the shared constructor contract, never real peer delivery.
        for kind in ("local","husk"):
            visuals=NativeVisuals();item=Item(kind+"-base");hand=Hand(visuals)
            hand.apply(item)
            self.assertEqual(item.tmp.resource,item.resource)
            self.assertIs(item.tmp.material,PLAYER_MATERIAL)
            hand.clear();self.assertIsNone(item.tmp)

    def test_failed_rotated_model_load_retains_base_fallback_without_more_construction(self):
        visuals=NativeVisuals();item=Item("rifle-base");hand=Hand(visuals)
        missing_pose_models={}
        for _ in range(10):hand.apply(item,missing_pose_models.get("rifle-up"))
        self.assertEqual(len(visuals.constructed),1)
        self.assertIs(item.tmp,hand.straight);self.assertEqual(item.tmp.resource,item.resource)
        # A base fallback does not establish the requested upward rendered pose.
        hand.clear();self.assertIsNone(item.tmp)

    def test_unequip_and_actor_clear_restore_each_hand_without_retaining_extra_cache(self):
        visuals=NativeVisuals();main=Item("pistol-main");off_original=Wrapper("pistol-off-original")
        off=Item("pistol-off",off_original);hands=[Hand(visuals),Hand(visuals)]
        hands[0].apply(main,Wrapper("main-kick"));hands[1].apply(off)
        hands[0].apply(None)
        self.assertIsNone(main.tmp);self.assertIsNone(hands[0].straight)
        hands[1].clear();self.assertIs(off.tmp,off_original)
        self.assertTrue(all(hand.item is None and hand.straight is None for hand in hands))

    def test_missing_base_resource_does_not_construct_in_a_hot_loop(self):
        visuals=NativeVisuals();item=Item(None);hand=Hand(visuals)
        for _ in range(100):hand.apply(item);self.assertIsNone(visuals.get_model(item))
        self.assertEqual(visuals.constructed,[]);self.assertIsNone(hand.original)
        hand.clear();self.assertIsNone(item.tmp)

    def test_source_lifetime_guard_keeps_constructor_inside_first_binding(self):
        source=(ROOT/"mods/firearms/scripts/HWP/Firearms/Pose.as").read_text()
        start=source.index("if (hand.m_item is null)")
        opening=source.index("{",start);depth=1;end=opening+1
        while depth:
            depth+=(source[end]=="{")-(source[end]=="}");end+=1
        constructor="CustomUnitModel(base, g_plrMat)"
        self.assertEqual(source.count(constructor),1)
        self.assertIn(constructor,source[opening:end])
        self.assertIn("@hand.m_was = item.m_modelTmp;",source[opening:end])
        self.assertIn("@hand.m_straight = hand.m_was;",source[opening:end])
        self.assertIn("CustomUnitModel@ want = hand.m_straight;",source)
        self.assertIn("HeldGunOn(m_plr)",source)
        for line in ("@hand.m_item.m_modelTmp = hand.m_was;",
                     "@m_main.m_item.m_modelTmp = m_main.m_was;","@m_off.m_item.m_modelTmp = m_off.m_was;"):
            self.assertIn(line,source)
        self.assertIn("@hand.m_straight = null;",source)
        self.assertIn("@m_main.m_straight = null;",source);self.assertIn("@m_off.m_straight = null;",source)


if __name__=="__main__":unittest.main()
