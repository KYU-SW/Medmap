# PROVENANCE

- pwd: `~/medmap`
- git commit: `a3253feac1135048c0afcc150863a2b5c2a93de0`
- git status:
```
 M .claude/MEMORY.md
?? .claude/memory/step15-v2-blind-profile-2026-09-21.md
?? exp/step15_v2_blind_profile/
?? exp/step15_v2_evaluation/
```
- PROFILE_FREEZE_V2 SHA256: `aa0be8c29cb9773ad4220825fe468442d158bbea85ac807b61e8d9a1a5118766`
- frozen pre/post unchanged: `True`
- DDXPlus inputs: `data/ddxplus/en/release_conditions.json`, `release_evidences.json`, `release_validate_patients`
- DDXPlus TEST: identified but never opened
- Step14 mechanical mapping: `exp/step14_value_context_recovery/07_evidence_value_level_map.csv` SHA256 `9e414e05a1899917976a4bab75a217f7a7e9a62cb9b1b9ef64f22a8d8a1697fa`
- Step14 columns read: `evidence_id, original_text, base_concept, attribute_location, attribute_severity, attribute_onset, attribute_duration, attribute_frequency, context_history, context_family, context_medication, context_exposure`
- Step13B mechanical relation matrix: `exp/step13b_external_verifier/00b_relation_matrix_nonzero.csv` SHA256 `f4de759916492fecaf0b7731e643f2e56a06c2c0d046237705d2aaa0266d1231`
- Step13B columns read: `ddxplus_disease, evidence_id, finding, strict_score`
- Python: `3.12.3`
- command: `/usr/bin/python3 step15v2_evaluate.py --root ~/medmap`
- random seed: `1502`
- timestamp UTC: `2026-09-21T15:04:31.788048+00:00`

## Input SHA256

- `data/ddxplus/en/release_conditions.json`: `56edf4682d8e86a4209fc3a33932e50ce03d1cc1fecc326c26d5ef8fa5c24890`
- `data/ddxplus/en/release_evidences.json`: `281c78b044ae60514e28ecc9052d08a8225dd3e2db3f00f8788b99c47b05e0c0`
- `data/ddxplus/en/release_validate_patients`: `b84733533bff01daa1d47d27a0cd4d684bb54a0fc20d80aaee1250ff8ff989ed`
- `exp/step14_value_context_recovery/07_evidence_value_level_map.csv`: `9e414e05a1899917976a4bab75a217f7a7e9a62cb9b1b9ef64f22a8d8a1697fa`
- `exp/step13b_external_verifier/00b_relation_matrix_nonzero.csv`: `f4de759916492fecaf0b7731e643f2e56a06c2c0d046237705d2aaa0266d1231`

## pip freeze

```
attrs==23.2.0
Automat==22.10.0
Babel==2.10.3
bcrypt==3.2.2
blinker==1.7.0
certifi==2023.11.17
chardet==5.2.0
click==8.1.6
cloud-init==25.2
colorama==0.4.6
command-not-found==0.3
configobj==5.0.8
constantly==23.10.4
cryptography==41.0.7
dbus-python==1.3.2
distro==1.9.0
distro-info==1.7+build1
httplib2==0.20.4
hyperlink==21.0.0
idna==3.6
incremental==22.10.0
Jinja2==3.1.2
jsonpatch==1.32
jsonpointer==2.0
jsonschema==4.10.3
launchpadlib==1.11.0
lazr.restfulclient==0.14.6
lazr.uri==1.0.6
lxml==6.1.1
markdown-it-py==3.0.0
MarkupSafe==2.1.5
mdurl==0.1.2
netifaces==0.11.0
numpy==2.4.6
oauthlib==3.2.2
pillow==12.2.0
pyasn1==0.4.8
pyasn1-modules==0.2.8
pycurl==7.45.3
Pygments==2.17.2
PyGObject==3.48.2
PyHamcrest==2.1.0
PyJWT==2.7.0
pyOpenSSL==23.2.0
pyparsing==3.1.1
pyrsistent==0.20.0
pyserial==3.5
python-apt==2.7.7+ubuntu5.1
python-pptx==1.0.2
pytz==2024.1
PyYAML==6.0.1
requests==2.31.0
rich==13.7.1
service-identity==24.1.0
setuptools==68.1.2
six==1.16.0
systemd-python==235
Twisted==24.3.0
typing_extensions==4.10.0
ubuntu-pro-client==8001
unattended-upgrades==0.1
urllib3==2.0.7
wadllib==1.3.6
wheel==0.42.0
xlsxwriter==3.2.9
zope.interface==6.1
```
