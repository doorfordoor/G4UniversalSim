"""Independent retained frozen-desktop receipt validation; no GUI launch."""
import argparse,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('candidate_install_checks',ROOT/'verify_installation.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('artifact_directory',type=Path);args=parser.parse_args()
    base=args.artifact_directory/'frozen-desktop-ci'
    delivery=v.load(base/'delivery.json')
    assert delivery['schema']=='g4usim_frozen_desktop_delivery_v1' and delivery['status']=='passed'
    selftest=v.load(base/'gui-self-test.json');assert selftest['ok'] and selftest['frozen']
    sources=v.load(base/'gui-build/source-identity.json')
    assert sources['stable'] and sources['sources_before']==sources['sources_after']
    source_identity=v.checkout_identities(sources['sources_before'])
    expected={'frozen-gui':0,'existing-gui-report':1,'frozen-python-root':0,'frozen-gui-import-failure':1}
    assert {r['name']:r['exit_code'] for r in delivery['commands']}==expected
    for row in delivery['commands']:
        path=base/row['log'];assert path.resolve().is_relative_to(base.resolve())
        assert v.sha(path)==row['log_sha256']
    receipt=dict(candidate_head=v.HEAD,platform=delivery['platform'],status='independently_verified',delivery_status=delivery['status'],source_identity=source_identity,command_raw_logs_sha_verified=True,expected_positive_and_negative_exit_codes=expected,gui_selftest_ok=True,frozen=True,scope=delivery['scope'])
    (ROOT/('desktop-'+delivery['platform']+'-checked.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(platform=receipt['platform'],status=receipt['status'],sources=source_identity['files'])))
if __name__=='__main__':main()
