# PROVENANCE — STEP 14 (2026-09-21)

- git commit: 21ff2aa6bd562770a74be61a1ae543b913b29339 (repo ~/medmap, git init at this step; data/ logs/ parquet/pkl/대용량 csv는 .gitignore)
- Python: Python 3.12.3, pip freeze: docs/environment_ai_env_pip_freeze_2026-09-21.txt
- 실행 command: `~/ai_env/bin/python exp/step14_value_context_recovery/s14a_taxonomy.py` → `s14b_analysis.py` → (요약 셀) ; 로그 logs/step14b_*.log
- random seed: partial view seed 42/43/44 (Step 2+3 저장본 재사용), ablation 임계 quantile(결정적). 신규 난수 없음
- TEST 사용: 0회 (validate·train 통계만)
- 외부 데이터 버전: UMLS 2026AA (MRCONSO/MRREL full zip sha256 041cae91…), SNOMED CT International 20260901, HPO release 2026-09-01 (hp.obo data-version), OptimusKG Dataverse doi:10.7910/DVN/IYNGEV v3.2(2026-09-09), HSDN Nat Commun 2014 Supp Data(raw/SHA256SUMS.txt), DisMech commit eaa5fe99bd0289e737d65646456d928b1f973282, hetio/medline commit 1cd80d12335b6550e18d5195507d62c9c924f04d, Wikidata SPARQL 2026-09-21, DDXPlus figshare 22687585

## 입력 파일 SHA256
- data/ddxplus/en/release_conditions.json  56edf4682d8e86a4209fc3a33932e50ce03d1cc1fecc326c26d5ef8fa5c24890
- data/ddxplus/en/release_evidences.json  281c78b044ae60514e28ecc9052d08a8225dd3e2db3f00f8788b99c47b05e0c0
- data/ddxplus/en/release_validate_patients  b84733533bff01daa1d47d27a0cd4d684bb54a0fc20d80aaee1250ff8ff989ed
- exp/step8_mapping/evidence_concept_map.csv  d00686208b48d16cac6d93f76beeb7e009c8144801ab4ddd170a1292c7d70e58
- exp/step8_mapping/evidence_semantics.tsv  dea4dcf4efb3e184f98c71c25ede80691f1831df35dcdf71e9594313176d2d61
- exp/step9_external_knowledge/03_evidence_eligibility.csv  487df34c2f3b96fb60ba5d508352f2d194bf83bbf134ce121b5175297e3e759f
- exp/step9_external_knowledge/01_disease_concept_map.csv  83037baf9487f66befe295519ebab7e5ec3b23a3889ff24f91d1343c661db87f
- exp/step9_external_knowledge/02_external_disease_finding_edges.csv  ce687daf4fb13e816390ea4e3732c1f18f813a8885d9aea00daf6211c940a10d
- exp/step10_hsdn/03_hsdn_disease_finding_edges.csv  32974fb095b3997c7c3dcf312d1001a04183911d660795cbe5a9a109c689b8ef
- exp/step10_hsdn/01_hsdn_disease_map.csv  9d123437c7b397379c37af6c1baf1edafae43463e5f06cef9c5e69e1e3a17e32
- exp/step11_external_expansion/01_umls_disease_finding_edges.csv  1f3c5ab879ab29555a561187b53839153c8f1f6389d357f63359ffd17ed347bc
- exp/step11_external_expansion/03_dismech_disease_finding_edges.csv  2b08f8e7a66701fc9db6b3d5d60b8c83f602b7609727aa68acee981c6eba0dc4
- exp/step11_external_expansion/06_medline_disease_finding_edges.csv  7f75a15a4ed49d7c322dd82ed41f3d7cf00d17bf8a41f28243907137aab9919c
- exp/step11_external_expansion/07_wikidata_disease_finding_edges.csv  5ea1a3c88e898162a41f6d9f13cc76120aead32162e2ff753f2d35968dcc1e86
- exp/step5_7_discrepancy/cond_token_logp.npz  42a66a562c77ded19e284ee2b915fc84c8e7eb6654ba4f1ba845351c1c501050
- exp/step2_3_workingdx/val_working_dx.parquet  20a6c7335b18fd2c55261d1a77773f78883629e3ed5c4f8dfed82cce0b597b6c
- exp/step2_3_workingdx/vocab.json  31b1cc6acbed4a896ee3ef4b8b2f56aae099a02ff205b9b36d6209aaccfc3c01

## 생성 파일 (행수, SHA256)
- 01_evidence_taxonomy.csv  rows=223  a0ed22da45fb1e236ba71502bdb8243e62d0fcd79643812d34f34af4401b381e
- 02_excluded_evidence_summary.csv  rows=15  7533d4ad4b80ae3bb813495d7759f35294a4d2d1356914a4f16d96011ef68d51
- 02b_excluded_evidence_examples.csv  rows=78  84c6dc72a58ec94f15d5cfe1953c5cf57196c410d604e0914eb34b7c1f908529
- 03_validation_ablation.csv  rows=132  4abadb1b13eb0b1cf3b6e99de19d233c0798fe5f839cbe61bdd2ba03dd660a3e
- 04_evidence_discriminative_value.csv  rows=515  f50f8dedee56d63339aab85228d7737d1161e8e22746026501dbdd18500a5390
- 05_error_pair_missing_information.csv  rows=10  4a2eb6a4bef68eee8c69aac1a3c3d27ea6636a85bb6a131dfdda63810e74e942
- 06_value_level_schema.md  rows=  33418f28d22f5028c2a55e583733c2e8dd463a64888ab1b456c3be9893cd397d
- 07_evidence_value_level_map.csv  rows=223  9e414e05a1899917976a4bab75a217f7a7e9a62cb9b1b9ef64f22a8d8a1697fa
- 08_manual_review_queue.csv  rows=161  7bf087aea6e12bead16a2073fa42f444cc90a4c168d8465d6b4e037282ed468a
- 09_expanded_eligibility.csv  rows=223  edce2973e09cff04e3f280144681b6b6aedbc23ad875cc167a39c4ca411b03ef
- 10_coverage_before_after.csv  rows=49  115b2620e0cd426218d86544497557e6f4a06fc3a42220bb9245167ed32bb6eb
- 11_reachability_validation.csv  rows=12  aecc7b4b765493239337c09d8595ae0a989ccc8e96e4bd16796e62b58d8e3833
- 12_error_pair_recoverability.csv  rows=10  de4814bdf76ba7a2a90270f4c2650f334486428d9cd0cb3bfa1f9cb15b8cc3a9
- s14a_taxonomy.py  rows=  fce5b9a0957039355292b7dafc3d20c90153a69502c7334712b374e9347deb38
- s14b_analysis.py  rows=  5d51894e2979c0bdc68c5fdd3d56ba11ee368cd510da0de2674773193a9752e9