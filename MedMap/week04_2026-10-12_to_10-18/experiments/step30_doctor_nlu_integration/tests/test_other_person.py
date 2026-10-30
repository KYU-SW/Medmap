import unittest

from _base import SIM, item_at, item_from, packet, supported_mention


class OtherPerson(unittest.TestCase):
    def test_regression_case(self):
        p = packet("엄마는 기침하고 저는 머리가 아파요.")
        self.assertEqual(item_at(p, "기침")["category"], "E")
        self.assertFalse(item_at(p, "기침")["eligibility"]["eligible"])
        h = item_at(p, "머리가 아파")
        self.assertEqual(h["category"], "A")
        self.assertTrue(h["eligibility"]["eligible"])

    def test_forced_other_and_multiple(self):
        for v, cat in (("OTHER_PERSON", "E"), ("MULTIPLE", "F")):
            m = supported_mention()
            m["experiencer"] = v
            it = item_from(m)
            self.assertEqual(it["category"], cat)
            self.assertFalse(it["eligibility"]["eligible"])

    def test_confirm_all_does_not_take_family(self):
        p = packet("엄마는 기침하고 저는 머리가 아파요.")
        after, _ = SIM.apply_decisions(p, SIM.policy_confirm_everything(p))
        self.assertNotIn("E_201", after["model_input"]["patient_state_delta"])


if __name__ == "__main__":
    unittest.main()
