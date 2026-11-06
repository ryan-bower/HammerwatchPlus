"""Negative controls for an observation oracle; never gameplay PASS evidence."""
import copy
import unittest

from gamelab.bots.qa_specs_static_native import PHASES, assemble_observation, evaluate_observation


def observation():
    phases = []
    times = (33, 550, 850, 900, 1400, 2300, 2500)
    hp = (15000, 14990, 14980, 14975, 14960, 14920, 14915)
    for name, t, health in zip(PHASES, times, hp):
        before = name == "before_tt"
        stack = 0 if before else 2 if t <= 900 else 3
        phases.append({"phase": name, "t": t, "now": 10000 + t, "stacks": stack,
                       "targets": [{"unit": unit, "valid": True, "dead": False, "hpMax": 15000, "hpExact": health} for unit in (1, 2, 3)],
                       "crits": [] if before else [{"type": 11, "text": "10!", "born": 10000 + t - 50}],
                       "projectiles": [] if before else [{"unit": 44, "x": 30, "y": 0}],
                       "tt_cd": 0 if t < 650 else 12000 - t, "mm_cd": max(0, 2000 - t) if t >= 1000 else 0,
                       "tt_crit": 1, "mm_crit": 0, "spell_crit": 0, "mana": 160 if before else 110 if t <= 900 else 95})
    samples = []
    for t in range(50, 2501, 50):
        samples.append({"t": t, "now": 10000 + t, "stacks": 1 if t < 500 else 2 if t < 1000 else 3,
                        "hp": [15000 - t / 30] * 3, "tt_cd": 0 if t < 650 else 12000 - t,
                        "mm_cd": max(0, 2000 - t) if t >= 1000 else 0, "new_crits": 1 if t >= 1400 else 0})
    return {"complete": True, "error": "", "truncated": False, "ms": 2500, "frames": len(samples),
            "tt_input_at": 10033, "mm_input_at": 10900, "tt_input_frames": 19, "mm_input_frames": 13,
            "phases": phases, "samples": samples}


class ObservationOracleTests(unittest.TestCase):
    def test_complete_mechanical_observation_is_accepted(self):
        self.assertTrue(all(ok for ok, _ in evaluate_observation(observation()).values()))

    def test_debug_acknowledgement_cannot_pass(self):
        self.assertFalse(any(ok for ok, _ in evaluate_observation({"ok": True, "stacks": 3, "crit_chance": 1}).values()))

    def test_hp_must_really_change(self):
        data = observation()
        for phase in data["phases"]:
            for target in phase["targets"]:
                target["hpExact"] = 15000
        result = evaluate_observation(data)
        self.assertFalse(result["first_crit"][0])
        self.assertFalse(result["later_crits"][0])
        self.assertFalse(result["overlap_one_bonus"][0])

    def test_extra_old_orb_bonus_is_not_retried_or_accepted(self):
        data = observation()
        for phase in data["phases"]:
            if phase["t"] >= 1400:
                phase["stacks"] = 4
        for sample in data["samples"]:
            if sample["t"] >= 1000:
                sample["stacks"] = 4
        result = evaluate_observation(data)
        self.assertTrue(result["first_crit"][0])
        self.assertTrue(result["old_orb_critical"][0])
        self.assertFalse(result["overlap_one_bonus"][0])

    def test_immortal_text_is_not_critical_proof(self):
        data = observation()
        for phase in data["phases"]:
            for text in phase["crits"]:
                text["text"] = "Immortal"
        result = evaluate_observation(data)
        self.assertFalse(result["first_crit"][0])
        self.assertFalse(result["old_orb_critical"][0])

    def test_other_spell_critical_chance_invalidates_control(self):
        data = observation()
        for phase in data["phases"]:
            phase["mm_crit"] = 0.2
        self.assertFalse(evaluate_observation(data)["setup"][0])

    def test_second_tt_activation_cannot_impersonate_old_cast(self):
        data = observation()
        data["samples"][39]["tt_cd"] = 12000
        self.assertFalse(evaluate_observation(data)["old_orb_critical"][0])

    def test_negative_projectile_ids_are_not_identity_proof(self):
        data = observation()
        for phase in data["phases"]:
            for projectile in phase["projectiles"]:
                projectile["unit"] = -1
        self.assertTrue(evaluate_observation(data)["old_orb_critical"][0])

    def test_chunked_retention_preserves_all_observations(self):
        data = observation()
        final = {key: value for key, value in data.items() if key not in ("samples", "phases")}
        final.update(tag="trial1", sample_count=len(data["samples"]), phase_count=len(PHASES))
        events = [{"ev": "qa_static_phase", "tag": "trial1", "data": row} for row in data["phases"]]
        events += [{"ev": "qa_static_samples", "tag": "trial1", "offset": offset, "samples": data["samples"][offset:offset + 16]}
                   for offset in range(0, len(data["samples"]), 16)]
        rebuilt = assemble_observation(events, final)
        self.assertTrue(all(ok for ok, _ in evaluate_observation(rebuilt).values()))
        self.assertEqual(rebuilt["samples"], data["samples"])
        incomplete = assemble_observation(events[:-1], final)
        self.assertFalse(evaluate_observation(incomplete)["complete"][0])

    def test_conflicting_chunk_cannot_pass(self):
        data = observation()
        final = {"tag": "trial1", "sample_count": 1, "phase_count": len(PHASES)}
        events = [{"ev": "qa_static_samples", "tag": "trial1", "offset": 0, "samples": [{"stacks": value}]} for value in (3, 4)]
        self.assertIn("conflicting", assemble_observation(events, final)["retention_error"])


if __name__ == "__main__":
    unittest.main()
