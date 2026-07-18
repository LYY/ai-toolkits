# Financial Systems Testing Evaluation Results

## Frozen Inputs

| Input | SHA-256 |
|---|---|
| `cases.json` | `0f5619b235392857fe5f2b2a85e2e5b82e82a2e7e33924ff5827a38c62feef11` |
| `tests/financial-systems-testing-eval/rubric.md` | `20beaf26cb626c59e687b98fe5361abab8c225777c01975d4bc0754b50f94dc6` |
| `tests/financial-systems-testing-eval/prompts/money-rounding-source-missing.md` | `4ebbc3c17d40505357c2610d97089e67dd17d8e1ecae6ed2bbedeb770eb017bd` |
| `tests/financial-systems-testing-eval/prompts/ledger-transfer-conservation.md` | `6c9dc10087522ba62a6588dff4fa0f443d7bc4aed506c971b952bde5a0eaf984` |
| `tests/financial-systems-testing-eval/prompts/trade-partial-fill-cancel-race.md` | `7fa00b2f926a7a4352e04233820830a0fd7f8b3c32a33572872f66907539029a` |
| `tests/financial-systems-testing-eval/prompts/payment-timeout-unknown-outcome.md` | `008602bc524bed6afeab2dfa5900e4c4f42c0adcb06b56b97a7803375cdfc4fc` |
| `tests/financial-systems-testing-eval/prompts/wallet-freeze-reversal.md` | `198ee9149aaa6b81f71f5498606cffbeb381f09ba44b51e7e96b82f6e3563d7c` |
| `tests/financial-systems-testing-eval/prompts/risk-liquidation-price-source.md` | `40863c554d89f7e10c7e32dc8c0ce3f4742279e94e62f56b7ed852b67992cf11` |
| `tests/financial-systems-testing-eval/prompts/credit-decision-replay.md` | `472feeadeafba25567aa1430ff9d015a89999dd7c576b51c7f145dcd355d7146` |
| `tests/financial-systems-testing-eval/prompts/settlement-partial-dvp-calendar.md` | `0e4a859f38fd1d3707b3fa8180cc59d776c74799780abd59878124242df8dae8` |
| `tests/financial-systems-testing-eval/prompts/reconciliation-break-correction.md` | `f56c891d4282d20ae4554db336c94025e6757be1b3e1d7e61cf231dd58dda162` |
| `tests/financial-systems-testing-eval/prompts/reference-data-effective-date.md` | `f065f32f2f0b3f1714d85c453eec40afe304760dcc6e07aa7d373aa7fd74f0a5` |
| `tests/financial-systems-testing-eval/prompts/generic-crud-tests.md` | `42d41f37b067d099ace00c7ec63035726625696b5e2f0f14f222ef7a81feb9f0` |
| `tests/financial-systems-testing-eval/prompts/generic-concurrency-test.md` | `89a7651566464e5f33fdfebc3f2a96cdb3472c3ee3508fcc040c49bc7831f408` |
| `tests/financial-systems-testing-eval/prompts/security-only-payment-api.md` | `bc501770b9b2abfd7f814f6260cadead7fbc325cbefc294883400c6df37a778a` |
| `tests/financial-systems-testing-eval/prompts/compliance-only-request.md` | `30e718539b94b4083a4a7e7451ce1ba19ab73c3ea9f6e13839696e23d0b755c6` |

## RED Baseline

| Case ID | Group | Producer session | Grader session | Prompt SHA-256 | Response SHA-256 | Rubric verdicts |
|---|---|---|---|---|---|---|
| `money-rounding-source-missing` | `money-ledger` | `ses_08e0d5f72ffe3soYpbSTPzOOTa` | `ses_08e086fd7ffepJtwD0Dj2kN3PK` | `4ebbc3c17d40505357c2610d97089e67dd17d8e1ecae6ed2bbedeb770eb017bd` | `7d86ae2b82af11474da3c9b098cc124ed68365a31f108edd1866b10e19744acd` | FSE-01=true, FSE-02=true, FSE-03=false, FSE-04=true, FSE-05=true, FSE-06=true, FSE-07=true, FSE-08=true |
| `ledger-transfer-conservation` | `money-ledger` | `ses_08e0d5f1affegW1OBTDuhNMrTr` | `ses_08e086fb0ffexNBIfGVXGfmMGW` | `6c9dc10087522ba62a6588dff4fa0f443d7bc4aed506c971b952bde5a0eaf984` | `b9e6cea57bbdce2770165e1a09d0321caea437a3f2a48053d89dd7bbe0ce1bdf` | FSE-01=true, FSE-02=true, FSE-03=false, FSE-04=true, FSE-05=true, FSE-06=true, FSE-07=true, FSE-08=true |
| `trade-partial-fill-cancel-race` | `transaction-lifecycle` | `ses_08e0d5efbffeV3SKMeASps2HGX` | `ses_08e086f72ffefp6A8Gx7bU4xXw` | `7fa00b2f926a7a4352e04233820830a0fd7f8b3c32a33572872f66907539029a` | `b4ee894ff371209b322026d8d0a1b8ad448996fade0fa506190983628bc03967` | FSE-01=true, FSE-02=true, FSE-03=false, FSE-04=true, FSE-05=true, FSE-06=true, FSE-07=true, FSE-08=true |
| `payment-timeout-unknown-outcome` | `transaction-lifecycle` | `ses_08e0d5edcffe9wtoDXbPKdjmeH` | `ses_08e054d52ffdjc8JTMnsVk2Sf8` | `008602bc524bed6afeab2dfa5900e4c4f42c0adcb06b56b97a7803375cdfc4fc` | `7fde3141fbd01ffc3a81a0d000ecb61860a7f12c7081c7cab6f4c0923cba2c87` | FSE-01=true, FSE-02=true, FSE-03=false, FSE-04=true, FSE-05=true, FSE-06=true, FSE-07=true, FSE-08=true |
| `wallet-freeze-reversal` | `transaction-lifecycle` | `ses_08e0d5ed3ffehcGVR02IOm6ZrR` | `ses_08e086f11ffeYtrxDt0LHFhrV5` | `198ee9149aaa6b81f71f5498606cffbeb381f09ba44b51e7e96b82f6e3563d7c` | `41e44a07b9ff26ae1ec4f5ed8a83ce68d2906775fcef4e2fd83a763ca6b26c54` | FSE-01=true, FSE-02=true, FSE-03=false, FSE-04=true, FSE-05=true, FSE-06=true, FSE-07=true, FSE-08=true |
| `risk-liquidation-price-source` | `risk-settlement` | `ses_08e0d125dffe4pUhMDdsd4bnTI` | `ses_08e080636ffegBwemU01iXDgIA` | `40863c554d89f7e10c7e32dc8c0ce3f4742279e94e62f56b7ed852b67992cf11` | `47da1b4a86cd8f7de1ecb8a64c3a17dd0a3d679406c86b1f9de995ee24a3e0ce` | FSE-01=true, FSE-02=false, FSE-03=false, FSE-04=false, FSE-05=false, FSE-06=true, FSE-07=true, FSE-08=true |
| `credit-decision-replay` | `risk-settlement` | `ses_08e0d11eeffejUbi6Am6BcUJRu` | `ses_08e08023cffe4VVWMQE3LjNri8` | `472feeadeafba25567aa1430ff9d015a89999dd7c576b51c7f145dcd355d7146` | `b7523de03ddc397a43aa8695d4364f3a712372b4deeedb59554e32f501362dd4` | FSE-01=true, FSE-02=true, FSE-03=false, FSE-04=true, FSE-05=false, FSE-06=true, FSE-07=true, FSE-08=true |
| `settlement-partial-dvp-calendar` | `risk-settlement` | `ses_08e0d10fcffelKh6WDTctObFEb` | `ses_08e07f587ffeWlC8xwLftGU4FU` | `0e4a859f38fd1d3707b3fa8180cc59d776c74799780abd59878124242df8dae8` | `c79e4a20a4f04d00f11d883cb27c1f4a02a9a51812d3cf9706d1aed9790931d5` | FSE-01=true, FSE-02=true, FSE-03=false, FSE-04=true, FSE-05=false, FSE-06=true, FSE-07=true, FSE-08=true |
| `reconciliation-break-correction` | `resilience-reference` | `ses_08e0cfdcdffeb5BDJLJd2qieDZ` | `ses_08e07df01ffeas4JPfRYU5Kd9S` | `f56c891d4282d20ae4554db336c94025e6757be1b3e1d7e61cf231dd58dda162` | `1885633b64612d0c08d4415753bf00dd5d6c804a20dc288cad5db866ba184e85` | FSE-01=true, FSE-02=true, FSE-03=false, FSE-04=true, FSE-05=false, FSE-06=true, FSE-07=true, FSE-08=true |
| `reference-data-effective-date` | `resilience-reference` | `ses_08e0cea24ffebNjPev6gcycamP` | `ses_08e07cf9affeTCC619uD342rBJ` | `f065f32f2f0b3f1714d85c453eec40afe304760dcc6e07aa7d373aa7fd74f0a5` | `e890e28b47e23196ccbbeb879467365de3c6e7cebe15afc087fcf548439bfcc5` | FSE-01=true, FSE-02=true, FSE-03=false, FSE-04=true, FSE-05=false, FSE-06=true, FSE-07=true, FSE-08=true |
| `generic-crud-tests` | `generic` | `ses_08e0cc6e5ffecDSyMIAgalRsQC` | `ses_08e0781effferFVXGsCXVMGLvz` | `42d41f37b067d099ace00c7ec63035726625696b5e2f0f14f222ef7a81feb9f0` | `49a069ac4d572b1a1393ce2325a036323de21a5e3c3a88672aab47e01721ef87` | FSE-01=false, FSE-02=true, FSE-06=false, FSE-08=true |
| `generic-concurrency-test` | `generic` | `ses_08e0cbaf1ffeGT0IPWJxeUmRBt` | `ses_08e07620affeE3lMsFo7qbQqWt` | `89a7651566464e5f33fdfebc3f2a96cdb3472c3ee3508fcc040c49bc7831f408` | `2da74b6116720b8f1513a9c2d80857b18883126ab129a130606c263b3a041864` | FSE-01=false, FSE-02=true, FSE-06=false, FSE-08=true |
| `security-only-payment-api` | `security` | `ses_08e0cb6f4ffeQEIk7H7NvzSYOh` | `ses_08e075484ffeDzGAiQOESTxtWw` | `bc501770b9b2abfd7f814f6260cadead7fbc325cbefc294883400c6df37a778a` | `c8c7d9c60f6c0d0d3bf4c6669fb9d387f04d1567e145582506bb2e9507bc3f35` | FSE-01=false, FSE-02=true, FSE-06=false, FSE-08=true |
| `compliance-only-request` | `compliance` | `ses_08e0cab5affeRF9xqHDQp1QqVC` | `ses_08e074fefffeW4gAeXvkT8gMPc` | `30e718539b94b4083a4a7e7451ce1ba19ab73c3ea9f6e13839696e23d0b755c6` | `92034dddf620b8e4809da7c4ae30f7aa7c785c281a9873e10efa4d4efb997a05` | FSE-01=true, FSE-06=true, FSE-07=false, FSE-08=false |

## GREEN Evaluation

Pending until T6.
