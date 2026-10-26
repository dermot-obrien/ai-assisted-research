# Guarantees

What the vault promises, each promise with the tests that prove it. Research results are going to rest on these, so none is a claim without a test: `tests/test_experiment_vault.py` reads this table and fails if a test it names does not exist, and the tests are written so that breaking the behaviour fails them. G1, G3, G4, G5, G6, G8, G12, G18, G19 and G21 were checked that way, by breaking the code on purpose and watching their tests fail. A change that weakens a guarantee changes this page in the same pull request.

The tests use a folder vault and, for Cloud Storage, a stand-in for `gcloud`. What has not been tested against a real bucket is said in the last section.

| Id | Guarantee | Proved by |
|---|---|---|
| G1 | Restored code is the recorded commit, bit for bit: restore checks out the commit and refuses when its git tree differs from the recorded `tree` | `test_restore_rebuilds_the_repository_without_the_original`, `test_restored_code_whose_tree_differs_from_the_record_is_refused`, `test_git_tree_hash_matches_git` |
| G2 | Code restores without the original repository or its remote, from the vault alone | `test_restore_rebuilds_the_repository_without_the_original`, `test_a_split_history_restores_from_every_branch` |
| G3 | A captured commit survives the deletion of its branch on the remote: it is tagged `vault/<commit12>` and the tag pushed | `test_the_tag_is_pushed_and_keeps_a_deleted_branch`, `test_a_tag_name_taken_by_another_commit_falls_back_to_the_full_id` |
| G4 | A repository's history is stored once; a later capture adds only the commits the vault lacks, and a capture of a commit the vault holds adds nothing | `test_code_is_kept_as_tagged_incremental_bundles` |
| G5 | Every repository the run used is captured: the main one, each `--repo`, and every submodule, recursively; a submodule that is not checked out stops the capture | `test_submodules_are_captured_and_restored`, `test_a_submodule_that_is_not_checked_out_is_refused`, `test_a_second_repository_restores_beside_the_first` |
| G6 | Uncommitted changes stop the capture, unless `--allow-dirty`, which stores them as a patch and untracked files, restored in place | `test_uncommitted_changes_are_refused_unless_allowed`, `test_a_dirty_capture_restores_the_patch_and_untracked_files`, `test_a_dag_file_in_the_repository_does_not_make_it_dirty` |
| G7 | A shallow clone, or `--code-storage archive`, is kept as a compressed snapshot whose tree is checked, and is byte-identical for the same commit | `test_a_shallow_clone_is_kept_as_a_compressed_snapshot`, `test_archive_storage_on_request_is_deterministic` |
| G8 | Restore writes the bytes the run read: it applies the capture machine's end-of-line settings (`core.autocrlf`, `core.eol`), never the restoring machine's. A snapshot (G7) holds the commit's own bytes, without end-of-line conversion | `test_restore_ignores_the_users_line_ending_settings`, `test_restore_writes_the_line_endings_the_run_read` |
| G9 | Every input under `--data` and output under `--outputs` is stored and restored at the same path; a path outside the repository stops the capture; a run keeps as outputs only the files it wrote | `test_capsule_pins_code_data_environment_and_outputs`, `test_restore_materialises_code_data_and_scripts`, `test_data_outside_the_repository_is_refused`, `test_outputs_left_by_an_earlier_run_are_not_kept` |
| G10 | The capsule records the command, seeds, result-changing environment variables, interpreter, package lock, metrics and result | `test_capsule_pins_code_data_environment_and_outputs`, `test_capture_records_a_run_that_already_happened` |
| G11 | The environment can be rebuilt with no package index, from vendored wheels | ci: The experiment vault captures, links, verifies and replays |
| G12 | Nothing stored is ever replaced: blobs, bundles and manifests are written once | `test_manifests_are_never_overwritten`, `test_the_vault_never_replaces_a_stored_file` |
| G13 | Each file is stored once, however many capsules use it | `test_blobs_are_stored_once` |
| G14 | A capsule id carries its manifest's hash, and the DAG records the full hash, so a substituted manifest is found | `test_capsule_id_carries_the_manifest_hash`, `test_verify_checks_the_hash_the_dag_records`, `test_capsule_is_appended_to_the_node` |
| G15 | Damage is found, never replayed: a corrupt or missing blob or bundle fails `verify` and restore | `test_verify_detects_a_corrupt_blob`, `test_a_corrupt_bundle_is_detected`, `test_a_missing_bundle_fails_verification`, `test_a_missing_bundle_in_the_chain_is_named` |
| G16 | Several clones and agents can capture into one vault at once, and every capsule still restores | `test_two_clones_share_one_vault`, `test_concurrent_appends_to_a_new_list_field_both_survive` |
| G17 | A replay's verdict is `identical`, `reproduced` (within the tolerance fixed at capture), `drifted` (exit 3) or `failed`, and is kept as a retest capsule | `test_replay_reproduces_and_records_a_retest`, `test_replay_reports_drift`, `test_retest_of_compares_a_new_run_with_an_old_capsule`, `test_retest_of_exits_3_when_the_result_drifts`, `test_tolerances` |
| G18 | Secrets are never recorded; the vault's own key reaches only its own gcloud calls, from a private file deleted when the command ends, never the experiment, the console or a capsule | `test_secret_environment_variables_are_not_recorded`, `test_a_key_in_the_environment_authenticates_only_the_vaults_gcloud_calls`, `test_a_malformed_key_is_named_without_printing_it`, `test_without_a_key_gcloud_uses_the_signed_in_account` |
| G19 | `--dry-run` changes nothing (no run, tag or upload) and names every problem at once | `test_a_ready_capture_changes_nothing`, `test_every_problem_is_named` |
| G20 | A failed tag push does not lose the capture: the bundles still hold the commit | `test_an_unreachable_remote_still_keeps_the_capsule` |
| G21 | Older capsules keep restoring; a capsule of a newer format is refused, not misread | `test_a_format_1_capsule_still_restores`, `test_a_newer_format_is_refused` |
| G22 | Every manifest matches the published JSON Schema | `test_manifest_matches_the_schema`; every test that reads a manifest checks it too |
| G23 | A Cloud Storage vault behaves as a folder vault | `test_round_trip_through_gcs` |

## Limits

These are not guaranteed, and the capsule records what is needed to see them:

- Bit-identical results on different hardware, or with non-deterministic GPU kernels: the capsule records the hardware, and the tolerance decides what counts as the same result.
- Inputs fetched from the network while the experiment runs: anything not written under `--data` or `--outputs` is not in the capsule.
- System libraries outside Python (a C library, a CUDA driver): the capsule records the platform and GPUs, not the libraries.
- A real Cloud Storage bucket: the `gcloud` commands are the ones the documentation gives and are tested against a stand-in that implements them. Run the round trip in [storage](storage.md) once when the bucket is created.
