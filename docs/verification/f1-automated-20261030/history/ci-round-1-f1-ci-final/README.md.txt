# F1 first frozen CI round — FAILED, not final acceptance

Frozen commit: cd0f44a8bf885609c3636e7b8b367982baf0debc.
The directory name was selected before execution; it does not imply success.

Linux run 41021459195 and M0 run 41021459196 finished failure. Each of four jobs passed 25 static cases and 38 of 39 GUI cases; gui_start_page failed the expected example plot selection assertion. Linux backend/integration did not run after the GUI failure. Eight reports and four original official artifact ZIPs are preserved; all four ZIP SHA-256 values matched the GitHub metadata. Original job logs and run/job/artifact metadata are present. No reports were edited or converted to passing.

The new asynchronous loading path loses the requested example plot: a read-only real GUI probe awaited actual completion and still found three of four examples on the wrong dataset. See out/collab/f1-start-page-async-probe.json. This is a product ordering defect, not merely a test sleep requirement.

A corrected freeze must use a separate evidence root. Keep this round intact.
