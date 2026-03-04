# Dataset Receipt - GCT-DS-001

- seed: 42
- run_date: 2026-05-10
- start_week: 2026-02-23
- total_batches: 60
- total_claims: 12120
- total_lines: 12115
- total_members: 12120
- total_providers: 60
- locked_batch_id_format: BATCH_<YYYYMMDD>_<VENDOR>_<LOB>_W<NN>

## Incident Batches
- W02 MEDICAID/VENDOR_A: BATCH_20260302_VENDOR_A_MEDICAID_W02
- W06 COMMERCIAL/VENDOR_B: BATCH_20260330_VENDOR_B_COMMERCIAL_W06
- W07 COMMERCIAL/VENDOR_C: BATCH_20260406_VENDOR_C_COMMERCIAL_W07
- W10 MEDICAID/VENDOR_A: BATCH_20260427_VENDOR_A_MEDICAID_W10

## Acceptance Checks
- PASS clean_weeks_outside_w02_w06_w07
- PASS manifest_references_exist
- PASS r901_dup_rate_gt_1pct
- PASS r902_elig_mismatch_gt_2pct
- PASS r903_volume_shift_gt_15pct
- PASS reserved_npi_not_in_reference_providers
- PASS reserved_npi_only_r007_w02
- PASS topology_60_batches
- PASS topology_combo_count_60
- PASS topology_one_batch_per_combo
- PASS volume_all_other_200
- PASS volume_w10_320
- PASS w02_exact_r001_r009
- PASS w02_no_other_rules
- PASS w06_exact_r010
- PASS w06_other_rules_clean
- PASS w07_other_rules_clean
- PASS w07_r011_keys_5
- PASS w07_r011_participants_10
- PASS w07_r012_r015_exact

## Batch Anomaly Guarantees
- R901 dup participation: 10/200 = 0.0500
- R902 elig mismatch: 6/200 = 0.0300
- R903 volume shift: 320/200 median baseline, deviation=0.6000

## Determinism Fingerprints (sha256)
- data_raw/encounters_header.csv: ab92b32658b27f9353048faffb52ba73396467b91297c4789ec5ebd847c5b162
- data_raw/encounters_lines.csv: b351669fc628e34bcd2bc0f707b5e59f36dd0eaac2b0f110cfeb88e7930f6472
- data_raw/reference_members.csv: 46ad9d14ccb65c23576bc1eca68cbd59f4ed7b19879ba2e8dfc37622ad067dc3
- data_raw/reference_providers.csv: 9035c1f99a5e06c94d4592b8c03c70c91f5a0d03f66146b0a3f17e43991e6ed9
- outputs/injection_manifest.json: a15c7472afbbc162ac7c21d02b9340fd432062b7bcaa3ff9556a4658811d6fb1
- outputs/story_map.csv: 2ca377481cefa809fde16d66cade98554de97c71946a76b5396ba852941c66c6
