"""Independent read-only-product review; writes only isolated temp fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gui"))
from g4usim_gui.core import workspace_recovery as recovery
from g4usim_gui.core.edit_snapshot import WorkspaceSnapshot, project_for_snapshot
from g4usim_gui.core.project import G4USimProject, project_to_dict
from g4usim_gui.editors.material_editor_model import MaterialDocument


def payload(name):
    project = G4USimProject(projectName=name)
    project.materialEditor = MaterialDocument()
    return project_to_dict(project_for_snapshot(WorkspaceSnapshot(project)))


def error(action):
    try:
        action()
    except Exception as exc:
        return type(exc).__name__, str(exc)
    return None


def claim_action(store, candidate, action):
    with store.claim(candidate) as claim:
        return getattr(claim, action)()


def main():
    facts = {}
    with tempfile.TemporaryDirectory(prefix="f5-independent-recovery-review-") as temporary:
        root = Path(temporary)
        store = recovery.RecoveryStore(root / "store")
        session = store.open_session()
        receipt = session.publish(payload("newer immutable snapshot"), 4)
        original = session.path.read_bytes()
        facts["lower_revision"] = error(lambda: session.publish(payload("old"), 3))
        assert facts["lower_revision"] and session.path.read_bytes() == original
        facts["same_revision_conflicting_payload"] = error(lambda: session.publish(payload("stale conflicting payload"), 4))
        same = json.loads(session.path.read_bytes())
        facts["same_revision_result"] = {"revision": same["revision"], "projectName": same["payload"]["projectName"]}
        # This assertion documents the reproduced weakness, not desired behavior.
        assert facts["same_revision_conflicting_payload"] is None and same["payload"]["projectName"] == "stale conflicting payload"
        session.retire("discarded")
        assert not session.path.exists()
        facts["retired_same_revision_publish"] = error(lambda: session.publish(payload("delayed discarded snapshot"), 4))
        facts["retired_copy_recreated"] = session.path.exists()
        assert facts["retired_same_revision_publish"] is None and facts["retired_copy_recreated"]
        session.close()
        candidates = store.discover()
        assert len(candidates) == 1
        facts["retired_recreated_disposition"] = candidates[0].disposition
        assert candidates[0].disposition == "active"
        facts["closed_session"] = error(lambda: session.publish(payload("closed"), 5))
        assert facts["closed_session"]
        candidate = candidates[0]
        other = recovery.RecoveryStore(root / "other")
        facts["non_own_claim"] = error(lambda: claim_action(other, candidate, "discard"))
        assert facts["non_own_claim"] and candidate.path.exists()
        with store.claim(candidate) as claim:
            assert not store.discover()
        facts["closed_claim_read"] = error(claim.read)
        facts["closed_claim_discard"] = error(claim.discard)
        assert facts["closed_claim_read"] and facts["closed_claim_discard"]

        live = store.open_session()
        live.publish(payload("keep old"), 1)
        before = live.path.read_bytes()
        for name in ("fsync", "replace"):
            with patch.object(recovery.os, name, side_effect=OSError("independent " + name + " failure")):
                facts["failure_" + name] = error(lambda: live.publish(payload("must not publish"), 2))
            assert facts["failure_" + name] and live.path.read_bytes() == before
        live.close()
        # An excessive regular recovery file is visible but has no claimable
        # fingerprint: even explicit discard is currently refused.
        excessive = root / "large"
        excessive_store = recovery.RecoveryStore(excessive)
        name = "a" * 32
        target = excessive / (name + ".json")
        target.write_bytes(b"x" * 2049)
        with patch.object(recovery, "MAX_BYTES", 2048):
            huge = excessive_store.discover()[0]
            facts["oversize_discovered"] = {"error": huge.error, "hash_present": bool(huge.raw_sha256)}
            facts["oversize_discard"] = error(lambda: claim_action(excessive_store, huge, "discard"))
            assert huge.error and not huge.raw_sha256 and facts["oversize_discard"] and target.exists()
        facts["scope"] = "pure storage API; controller queue reachability not claimed"
    output = ROOT / "out/collab/f5-recovery-review-repro.json"
    output.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(facts, ensure_ascii=False))


if __name__ == "__main__":
    main()
