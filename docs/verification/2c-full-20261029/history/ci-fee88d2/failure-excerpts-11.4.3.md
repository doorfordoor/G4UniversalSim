## run_summary

`out\verification\2c-ci\linux-evidence-11.4.3\linux-backend\20261029-134341-cbefea7b\run_summary.log`

```text
  File "/home/runner/work/G4UniversalSim/G4UniversalSim/tools/test_assert_probe.py", line 153, in main
    runpy.run_path(str(target), run_name="__main__")
  File "<frozen runpy>", line 291, in run_path
  File "<frozen runpy>", line 98, in _run_module_code
  File "<frozen runpy>", line 88, in _run_code
  File "/home/runner/work/G4UniversalSim/G4UniversalSim/scripts/test_run_summary.py", line 1604, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "/home/runner/work/G4UniversalSim/G4UniversalSim/scripts/test_run_summary.py", line 626, in main
    assert read_generated_file_schemas(dry_output) == {
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError
```

## sd_context_failure

`out\verification\2c-ci\linux-evidence-11.4.3\linux-backend\20261029-134341-cbefea7b\sd_context_failure.log`

```text
    runpy.run_path(str(target), run_name="__main__")
  File "<frozen runpy>", line 291, in run_path
  File "<frozen runpy>", line 98, in _run_module_code
  File "<frozen runpy>", line 88, in _run_code
  File "/home/runner/work/G4UniversalSim/G4UniversalSim/scripts/test_sd_context_failure.py", line 87, in <module>
    main()
  File "/home/runner/work/G4UniversalSim/G4UniversalSim/scripts/test_sd_context_failure.py", line 82, in main
    run_case(work, threads, fault)
  File "/home/runner/work/G4UniversalSim/G4UniversalSim/scripts/test_sd_context_failure.py", line 60, in run_case
    assert completed.returncode == 1, (name, completed.returncode, log[-3000:])
           ^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: ('2-sd_context_t0', 0, '===============================================\nType of pre-compound model                          0\nType of pre-compound inverse x-section              1\nPre-compound model active                           1\nPre-compound excitation low energy             ... [long line omitted; original log retained] ... ] {"schema":"g4usim_progress_v1","run_id":2,"sequence":6,"phase":"end","planned_events":10,"completed_events":10,"elapsed_s":0.058580557,"rate_eps":170.7051027,"eta_s":0}\n     Cr_sctns:  Glauber-Gribov Nucl-nucl: 0 eV  ---> 25.6 PeV\n     Cr_sctns:  Glauber-Gribov Nucl-nucl: 0 eV  ---> 25.6 PeV\n')
```

## displacement_damage

`out\verification\2c-ci\linux-evidence-11.4.3\linux-backend\20261029-134341-cbefea7b\displacement_damage.log`

```text
  File "/home/runner/work/G4UniversalSim/G4UniversalSim/tools/test_assert_probe.py", line 153, in main
    runpy.run_path(str(target), run_name="__main__")
  File "<frozen runpy>", line 291, in run_path
  File "<frozen runpy>", line 98, in _run_module_code
  File "<frozen runpy>", line 88, in _run_code
  File "/home/runner/work/G4UniversalSim/G4UniversalSim/scripts/test_displacement_damage.py", line 231, in <module>
    sys.exit(main())
             ^^^^^^
  File "/home/runner/work/G4UniversalSim/G4UniversalSim/scripts/test_displacement_damage.py", line 203, in main
    assert message in log, (message, log[-2000:])
           ^^^^^^^^^^^^^^
AssertionError: ('cannot open NIEL table', "G4UniversalSim fatal error: [scoring.displacement]/proton (/tmp/g4usim_ddd_os_3e137/case05.ini line 28): Input file does not exist or is not regular: '/tmp/g4usim_ddd_os_3e137/missing.csv'\n")
```

## interactive_commands

`out\verification\2c-ci\linux-evidence-11.4.3\linux-backend\20261029-134341-cbefea7b\interactive_commands.log`

```text
  File "/home/runner/work/G4UniversalSim/G4UniversalSim/tools/test_assert_probe.py", line 153, in main
    runpy.run_path(str(target), run_name="__main__")
  File "<frozen runpy>", line 291, in run_path
  File "<frozen runpy>", line 98, in _run_module_code
  File "<frozen runpy>", line 88, in _run_code
  File "/home/runner/work/G4UniversalSim/G4UniversalSim/scripts/test_interactive_commands.py", line 437, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "/home/runner/work/G4UniversalSim/G4UniversalSim/scripts/test_interactive_commands.py", line 171, in main
    assert result["effective_threads_origin_kind"] == "runtime_unattributed", result
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: {'actual_completed_event_count': '2', 'actual_macro_file': 'unknown', 'actual_output_dir': '/tmp/g4usim-interactive-fvohf0ul/threads_before_init', 'actual_threads': '2', 'biasing_attached_operator_count': '0', 'biasing_attachment_scope': 'master_geometry', 'biasing_effect_observed':  ... [long line omitted; original log retained] ... _20_schema': 'run_metadata_json_v1', 'file_21_path': '/tmp/g4usim-interactive-fvohf0ul/threads_before_init/run_summary.txt', 'file_21_schema': 'run_summary_v1', 'file_22_path': '/tmp/g4usim-interactive-fvohf0ul/threads_before_init/scorer_statistics.csv', 'file_22_schema': 'scorer_statistics_csv_v2'}
```
