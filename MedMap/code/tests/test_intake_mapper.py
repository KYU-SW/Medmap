"""Natural Intake v1 매퍼 회귀 테스트 — alias·부정 범위·중복·겹침·미지원 문구·계약 검증."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medmap import config
from medmap.intake import AliasValidationError, IntakeMapper, load_aliases
from medmap.intake.mapper import ALIASES_JSON

MAPPER = IntakeMapper()
CATALOG = json.loads(Path(config.EVIDENCES_JSON).read_text())
KO_LABELS = json.loads((ROOT / "medmap" / "data" / "question_labels_ko.json").read_text())["questions"]


def pairs(text):
    return {(r["evidence_id"], r["status"]) for r in MAPPER.extract(text)}


def write_aliases(entries, **extra):
    spec = json.loads(ALIASES_JSON.read_text())
    spec["entries"] = entries
    spec.update(extra)
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(spec, f, ensure_ascii=False)
    f.close()
    return f.name


class AliasPositiveNegativeTests(unittest.TestCase):
    def test_01_exact_alias_positive(self):
        self.assertEqual(pairs("기침이 나요."), {("E_201", "POSITIVE")})
        self.assertEqual(pairs("열이 있어요"), {("E_91", "POSITIVE")})

    def test_02_exact_alias_negative(self):
        self.assertEqual(pairs("열은 없어요."), {("E_91", "NEGATIVE")})
        self.assertEqual(pairs("기침은 안 나요"), {("E_201", "NEGATIVE")})
        self.assertEqual(pairs("메스껍지는 않아요"), {("E_148", "NEGATIVE")})

    def test_03_negation_forms(self):
        for text in ["열은 없다", "열은 없어요", "열은 없습니다", "기침은 안 난다", "기침은 안 나요", "기침은 아니에요",
                     "기침은 아니다", "기침은 괜찮다", "기침은 괜찮아요", "기침을 하지 않는다", "기침을 하지 않아요"]:
            got = MAPPER.extract(text)
            self.assertEqual(len(got), 1, text)
            self.assertEqual(got[0]["status"], "NEGATIVE", text)
            self.assertEqual(got[0]["source"], "ALIAS_NEGATION", text)

    def test_04_output_schema(self):
        r = MAPPER.extract("기침이 나고 열은 없어요.")
        self.assertEqual([x["evidence_id"] for x in r], ["E_201", "E_91"])
        for x in r:
            self.assertEqual(x["confidence"], "HIGH")
            self.assertTrue({"evidence_id", "status", "matched_text", "source", "confidence"} <= set(x))
        self.assertEqual(r[1]["matched_text"], "열은 없어요")


class NegationScopeTests(unittest.TestCase):
    def test_10_mixed_positive_negative(self):
        self.assertEqual(pairs("열은 없는데 기침은 나요."), {("E_91", "NEGATIVE"), ("E_201", "POSITIVE")})
        self.assertEqual(pairs("기침은 나는데 열은 없어요"), {("E_201", "POSITIVE"), ("E_91", "NEGATIVE")})

    def test_11_negation_does_not_spread_across_clause(self):
        # "안"이 문장에 있어도 다른 절이면 영향 없음
        self.assertEqual(pairs("숨이 차서 밥을 안 먹어요"), {("E_66", "POSITIVE")})
        self.assertEqual(pairs("기침이 나서 잠을 못 자요"), {("E_201", "POSITIVE")})

    def test_12_persistence_verbs_are_positive(self):
        self.assertEqual(pairs("열이 안 떨어져요"), {("E_91", "POSITIVE")})
        self.assertEqual(pairs("콧물이 안 멈춰요"), {("E_181", "POSITIVE")})
        self.assertEqual(pairs("기침이 멈추지 않아요"), {("E_201", "POSITIVE")})

    def test_13_coordinated_nouns_share_predicate(self):
        self.assertEqual(pairs("기침, 콧물, 열이 있어요"), {("E_201", "POSITIVE"), ("E_181", "POSITIVE"), ("E_91", "POSITIVE")})
        self.assertEqual(pairs("기침이랑 열은 없어요"), {("E_201", "NEGATIVE"), ("E_91", "NEGATIVE")})

    def test_14_ambiguous_coordination_negative_is_dropped(self):
        # "기침하고 열은 없어요": 기침이 동사인지 병렬인지 모호 → 기침은 버린다
        self.assertEqual(pairs("기침하고 열은 없어요"), {("E_91", "NEGATIVE")})

    def test_15_uncertain_negation_dropped(self):
        for text in ["기침은 별로 안 나요", "열이 없지 않아요", "열은 없는 것 같아요", "기침이 좀 나아졌어요"]:
            self.assertEqual(MAPPER.extract(text), [], text)

    def test_16_partial_body_denial_is_not_global_pain_negative(self):
        # "머리는 안 아파요"는 다른 곳 통증을 부정하지 않는다 → E_53 NEGATIVE 금지
        self.assertEqual(pairs("머리는 안 아파요"), set())
        self.assertEqual(pairs("통증은 없어요"), {("E_53", "NEGATIVE")})


class DedupOverlapTests(unittest.TestCase):
    def test_20_duplicated_synonym_dedup(self):
        r = MAPPER.extract("기침이 나요. 콜록콜록 기침을 계속 해요.")
        self.assertEqual([(x["evidence_id"], x["status"]) for x in r], [("E_201", "POSITIVE")])

    def test_21_conflicting_mentions_dropped(self):
        self.assertEqual(pairs("열이 나요. 열은 없어요."), set())

    def test_22_overlapping_alias_longest_wins(self):
        # "누런 콧물"은 E_182 하나로, 안쪽 "콧물"(E_181)을 따로 내지 않는다
        self.assertEqual(pairs("누런 콧물이 나와요"), {("E_182", "POSITIVE")})
        # "기침할 때 피가" → E_45만, 안쪽 기침(E_201) 별도 생성 없음
        self.assertEqual(pairs("기침할 때 피가 섞여 나와요"), {("E_45", "POSITIVE")})

    def test_23_implied_pain_only_on_positive(self):
        self.assertEqual(pairs("움직이면 가슴이 아파요"), {("E_216", "POSITIVE"), ("E_53", "POSITIVE")})
        # v1.2: E_216은 통증 전제 조건부 evidence라 negative_policy에서 UNSAFE → NEGATIVE 반환 안 함
        self.assertEqual(pairs("움직여도 안 아파요"), set())


class NoInventionTests(unittest.TestCase):
    def test_30_unsupported_phrase_produces_no_result(self):
        for text in ["몸이 안 좋아요", "감기 같아요", "독감인가 봐요", "오늘 날씨가 좋네요", "코피가 나요",
                     "기침약을 먹었어요", "열심히 운동해요", "땀띠가 났어요", "열 번이나 전화했어요"]:
            self.assertNotIn("E_50", {r["evidence_id"] for r in MAPPER.extract(text)}, text)
            if text != "땀띠가 났어요":
                self.assertEqual(MAPPER.extract(text), [], text)

    def test_31_other_person_question_hedge_conditional(self):
        for text in ["동생이 기침을 해요", "열이 나면 병원 가야 하나요?", "혹시 열이 있을까요",
                     "열이 있는 것 같기도 하고 아닌 것 같기도 해요", "기침할 때마다 목이 쉬려나"]:
            self.assertEqual(MAPPER.extract(text), [], text)

    def test_32_no_evidence_invented(self):
        texts = ["기침이 나고 열은 없어요.", "콧물이 줄줄 나고 목이 아파요", "숨이 차고 가슴이 두근거려요",
                 "감기에 걸렸어요", "당뇨가 있고 담배는 안 피워요"]
        for t in texts:
            for r in MAPPER.extract(t):
                self.assertIn(r["evidence_id"], MAPPER.supported, t)
                self.assertIn(r["evidence_id"], CATALOG, t)
                self.assertNotIn(r["evidence_id"], config.EXCLUDED_QUESTIONS, t)
                if r["source"] != "ALIAS_IMPLIED":
                    self.assertIn(r["matched_text"].split(" ")[0][:1], t, t)

    def test_33_deterministic_output(self):
        text = "열은 없는데 기침은 나고 콧물이랑 가래는 없어요. 움직이면 가슴이 아파요"
        first = MAPPER.extract(text)
        for _ in range(5):
            self.assertEqual(IntakeMapper().extract(text), first)
            self.assertEqual(MAPPER.extract(text), first)


class V11RegressionTests(unittest.TestCase):
    """v1 평가에서 확인된 오류 유형(A~F) 회귀 테스트. 기대 evidence/status를 명시."""

    def test_50_mixed_negation_scope_kept(self):
        self.assertEqual(pairs("열은 없는데 기침은 나요."), {("E_91", "NEGATIVE"), ("E_201", "POSITIVE")})

    def test_51_A_preverbal_an_applies_to_following_predicate(self):
        self.assertEqual(pairs("속이 안 울렁거려요."), {("E_148", "NEGATIVE")})
        self.assertEqual(pairs("속은 안 울렁거려요."), {("E_148", "NEGATIVE")})
        self.assertEqual(pairs("안 기침해요"), {("E_201", "NEGATIVE")})
        self.assertEqual(pairs("숨이 안 차요"), {("E_66", "NEGATIVE")})
        # 앞 절의 '안'은 뒤 mention에 번지지 않음
        self.assertEqual(pairs("밥은 안 먹었는데 속이 울렁거려요"), {("E_148", "POSITIVE")})

    def test_52_B_mot_is_not_blanket_negation(self):
        # 짧은 '못 V' = 증상 자체
        self.assertEqual(pairs("숨을 잘 못 쉬어요"), {("E_66", "POSITIVE")})
        self.assertEqual(pairs("숨을 못 쉬겠어요"), {("E_66", "POSITIVE")})
        self.assertEqual(pairs("기침을 못 멈춰요"), {("E_201", "POSITIVE")})
        # 긴 부정 'V-지 못하다' = 부정
        self.assertEqual(pairs("예방접종을 다 맞지는 못했어요."), {("E_209", "NEGATIVE")})

    def test_53_C_anin_scoped_to_its_mention(self):
        self.assertEqual(pairs("열은 아닌데 기침은 해요."), {("E_91", "NEGATIVE"), ("E_201", "POSITIVE")})
        self.assertEqual(pairs("알레르기 체질은 아닌데 콧물이 나요."), {("E_226", "NEGATIVE"), ("E_181", "POSITIVE")})
        self.assertEqual(pairs("기침은 아니고 콧물이 나요"), {("E_201", "NEGATIVE"), ("E_181", "POSITIVE")})
        # '~만 ~게 아니라'(뿐 아니라) → 부정으로 읽지 않음
        self.assertEqual(pairs("기침만 나는 게 아니라 열도 나요"), {("E_91", "POSITIVE")})

    def test_54_D_persistent_expressions_positive(self):
        self.assertEqual(pairs("기침이 안 멎어요."), {("E_201", "POSITIVE")})
        self.assertEqual(pairs("붓기가 안 빠져요."), {("E_151", "POSITIVE")})
        self.assertEqual(pairs("코막힘이 안 풀려요"), {("E_181", "POSITIVE")})
        self.assertEqual(pairs("몸살기운이 안 가셔요"), {("E_175", "POSITIVE")})

    def test_55_E_tense_rule_current_only_past_contrast_dropped(self):
        # 고정 규칙: 현재 상태만. 과거-현재 대비 문장의 (과거력 아닌) 증상은 반환하지 않는다(UNASKED)
        for text in ["어제는 열이 있었는데 지금은 없어요.", "며칠 전엔 기침을 심하게 했는데 지금은 괜찮아요.",
                     "저번주까지 몸살기운이 있었는데 지금은 멀쩡해요.", "열이 있었는데 지금은 없어요"]:
            self.assertEqual(MAPPER.extract(text), [], text)
        # '부터'는 현재 진행
        self.assertEqual(pairs("어제부터 열이 나요"), {("E_91", "POSITIVE")})
        # 과거력 질문 evidence는 질문의 시간 범위를 따른다
        self.assertEqual(pairs("예전에 천식이 있었어요"), {("E_124", "POSITIVE")})
        self.assertEqual(pairs("담배는 끊었어요"), {("E_79", "NEGATIVE")})

    def test_56_F_E112_not_overextended(self):
        self.assertEqual(pairs("숨소리가 좀 거칠어요."), set())
        self.assertEqual(pairs("기침한 뒤에 숨소리가 거칠어요"), {("E_112", "POSITIVE")})


class V12NegativePolicyTests(unittest.TestCase):
    """v1.2: NEGATIVE는 negative_policy.json allowlist evidence에서만. blind v2 확인 오류 유형 회귀."""
    POLICY = json.loads((ROOT / "medmap" / "intake" / "negative_policy.json").read_text())

    def test_60_policy_covers_supported_exactly_and_default_abstain(self):
        self.assertEqual(self.POLICY["default"], "ABSTAIN")
        ids = [e["evidence_id"] for e in self.POLICY["evidence"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(MAPPER.supported))
        for e in self.POLICY["evidence"]:
            self.assertIsInstance(e["negative_allowed"], bool)
            self.assertTrue(e["reason"])
            if e["reason"].startswith(("or_question", "and_compound", "conditional_modifier")):
                self.assertFalse(e["negative_allowed"], e["evidence_id"])

    def test_61_or_evidence_one_side_denied_is_unasked(self):
        self.assertEqual(pairs("천식은 없어요"), set())            # E_124 = 천식 OR 기관지확장제
        self.assertEqual(pairs("콧물은 안 나요"), set())            # E_181 = 코막힘 OR 맑은 콧물
        self.assertEqual(pairs("림프절은 안 부었어요"), set())        # E_9 = 붓거나 OR 아픔
        self.assertEqual(pairs("고혈압은 없어요"), set())           # E_104 = 고혈압 OR 혈압약

    def test_62_or_evidence_fully_denied_still_unasked_when_unsafe(self):
        # 전체 부정이어도 unsafe evidence는 NEGATIVE를 반환하지 않는다(사용자 확인 질문 몫)
        self.assertEqual(pairs("코가 막히거나 콧물이 나지는 않아요"), set())

    def test_63_unsafe_negative_never_returned(self):
        unsafe = {e["evidence_id"] for e in self.POLICY["evidence"] if not e["negative_allowed"]}
        texts = ["천식은 없어요", "심근경색은 없었어요", "피부에 발진은 없어요", "목소리는 괜찮아요", "두근거림은 없어요",
                 "코는 안 가려워요", "몸살은 없어요", "움직여도 안 아파요", "숨을 깊게 쉬어도 안 아파요", "림프절은 안 부었어요"]
        for t in texts:
            for r in MAPPER.extract(t):
                self.assertFalse(r["status"] == "NEGATIVE" and r["evidence_id"] in unsafe, (t, r))

    def test_64_safe_negative_clear_denial(self):
        self.assertEqual(pairs("열은 없어요"), {("E_91", "NEGATIVE")})
        self.assertEqual(pairs("가래는 안 나와요"), {("E_77", "NEGATIVE")})
        self.assertEqual(pairs("담배는 안 피워요"), {("E_79", "NEGATIVE")})
        self.assertEqual(pairs("메스껍지는 않아요"), {("E_148", "NEGATIVE")})

    def test_65_idiom_not_negation(self):
        self.assertEqual(pairs("장난 아니게 아파요"), {("E_53", "POSITIVE")})
        self.assertEqual(pairs("머리가 장난 아니게 아파요"), {("E_53", "POSITIVE")})
        self.assertEqual(pairs("기침이 끊임없이 나요"), {("E_201", "POSITIVE")})
        self.assertNotIn(("E_50", "NEGATIVE"), pairs("땀이 장난 아니게 나"))

    def test_66_mot_by_predicate(self):
        self.assertEqual(pairs("통증은 못 느꼈어요"), {("E_53", "NEGATIVE")})
        self.assertEqual(pairs("숨을 못 쉬겠어요"), {("E_66", "POSITIVE")})

    def test_67_apeunde_connective_not_location(self):
        # '아픈데'(연결어미) ≠ '아픈 데'(곳) → E_53 NEGATIVE로 오인 금지
        self.assertNotIn(("E_53", "NEGATIVE"), pairs("종아리가 부어서 욱신욱신 아픈데 피부는 괜찮아요"))
        self.assertEqual(pairs("아픈 데는 없어요"), {("E_53", "NEGATIVE")})
        self.assertEqual(pairs("아픈데는 없어요"), {("E_53", "NEGATIVE")})

    def test_68_disjunctive_geona_scope(self):
        self.assertEqual(pairs("기침하거나 열이 나는 건 아니에요"), {("E_201", "NEGATIVE"), ("E_91", "NEGATIVE")})
        self.assertEqual(pairs("기침하거나 열이 나요"), {("E_91", "POSITIVE")})       # 긍정 선언의 '거나' → 기침 버림
        self.assertEqual(pairs("기침하거나 힘줘도 더 아프지는 않아요"), set())         # 조건절 속 기침

    def test_69_v2_types_conditional_worry_past_inverted(self):
        self.assertEqual(pairs("기침할 때도 더 아파요"), set())
        self.assertEqual(pairs("가래에 피가 섞여 나올까 봐 걱정인데 피는 안 보였어요"), set())
        self.assertEqual(pairs("그땐 열이 났었어요"), set())
        self.assertEqual(pairs("어제까지는 콧물만 났는데 오늘부터 기침해요"), set())
        self.assertEqual(pairs("안나요 열은."), set())
        self.assertEqual(pairs("없어요, 열은."), set())
        self.assertEqual(pairs("열이 나요. 기침."), {("E_91", "POSITIVE"), ("E_201", "POSITIVE")})
        self.assertEqual(pairs("앞으로 숙이면 나아져요"), {("E_33", "POSITIVE")})    # 통증 명시 없음 → E_53 없음

    def test_70_invalid_policy_rejected(self):
        spec = json.loads((ROOT / "medmap" / "intake" / "negative_policy.json").read_text())
        for bad in [dict(spec, default="ALLOW"), dict(spec, evidence=spec["evidence"][:-1]),
                    dict(spec, evidence=spec["evidence"] + spec["evidence"][:1])]:
            f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
            json.dump(bad, f, ensure_ascii=False)
            f.close()
            with self.assertRaises(AliasValidationError):
                IntakeMapper(negative_policy_json=f.name)


class AliasContractTests(unittest.TestCase):
    def test_40_aliases_all_point_to_real_catalog_ids(self):
        aliases, history_ok = load_aliases()
        for a in aliases:
            self.assertIn(a.evidence_id, CATALOG)
            self.assertEqual(CATALOG[a.evidence_id]["data_type"], "B")
            self.assertNotIn(a.evidence_id, config.EXCLUDED_QUESTIONS)
            for j in a.implies_positive:
                self.assertIn(j, CATALOG)
        self.assertTrue(history_ok <= set(CATALOG))
        # v1 지원 범위 = freeze(2372e2f) 당시 한국어 질문 라벨이 있던 binary evidence 41개(고정 스냅샷).
        # 한국어 질문 표시문(question_labels_ko.json)은 terminology 정본에서 생성되며 223개로 늘었으므로
        # 표시 파일이 아니라 이 스냅샷과 비교한다(매퍼 지원 범위는 alias 파일에서만 정해진다).
        frozen_supported = {"E_0", "E_9", "E_33", "E_45", "E_50", "E_53", "E_66", "E_69", "E_70", "E_77", "E_78",
                            "E_79", "E_88", "E_89", "E_91", "E_104", "E_105", "E_112", "E_116", "E_120", "E_123",
                            "E_124", "E_129", "E_148", "E_151", "E_155", "E_169", "E_175", "E_181", "E_182",
                            "E_189", "E_194", "E_201", "E_209", "E_212", "E_214", "E_216", "E_218", "E_220",
                            "E_221", "E_226"}
        self.assertEqual(MAPPER.supported, frozen_supported)
        self.assertEqual(len(MAPPER.supported), 41)
        self.assertTrue(frozen_supported <= set(KO_LABELS))          # 지원 항목은 여전히 한국어 질문을 가진다

    def test_41_invalid_evidence_alias_rejected(self):
        bad = [
            [{"id": "x", "evidence_id": "E_99999", "pattern": "기침"}],          # 없는 ID
            [{"id": "x", "evidence_id": "E_134", "pattern": "기침"}],            # 제외 ID
            [{"id": "x", "evidence_id": "E_55", "pattern": "기침"}],             # non-binary
            [{"id": "x", "evidence_id": "E_201", "pattern": "기침("}],           # 잘못된 regex
            [{"id": "x", "evidence_id": "E_201", "pattern": "(?:기침)?"}],       # 빈 문자열 매치
            [{"id": "x", "evidence_id": "E_201", "pattern": "기침", "status": "MAYBE"}],
            [{"id": "x", "evidence_id": "E_201", "pattern": "기침", "implies_positive": ["E_152"]}],
            [{"id": "x", "evidence_id": "E_201", "pattern": "기침"}, {"id": "x", "evidence_id": "E_91", "pattern": "열"}],
            [],
        ]
        for entries in bad:
            with self.assertRaises(AliasValidationError, msg=str(entries)):
                IntakeMapper(aliases_json=write_aliases(entries))

    def test_42_forbidden_catalog_path_rejected(self):
        with self.assertRaises(config.MedMapForbiddenPath):
            IntakeMapper(evidences_json=config.DATA_DIR / "release_conditions.json")


if __name__ == "__main__":
    unittest.main()
