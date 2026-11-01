"""OUT/sibling-only archival restore; restored old MD is not public navigation."""
import argparse,hashlib,json,shutil
from pathlib import Path

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--destination',type=Path,required=True);ap.add_argument('--execute',action='store_true');a=ap.parse_args();root=Path(__file__).resolve().parent.parent;dest=a.destination.resolve();guard=root.parent.resolve();assert dest.is_relative_to(guard) and not dest.is_relative_to(root),'restore must be a fresh independent sibling';assert not dest.exists(),'refuse overwrite';m=json.loads((root/'manifest.json').read_text());print(json.dumps({'mode':'execute' if a.execute else 'dry-run','restorable_files':len(m['entries']),'destination':str(dest),'excluded_images_or_ZIPs_not_restored':True,'restored_old_MD_not_public_navigation':True}))
 if not a.execute:return
 dest.mkdir()
 for e in m['entries']:
  p=root/e['object'];assert hashlib.sha256(p.read_bytes()).hexdigest()==e['sha256'];q=(dest/e['original_logical_path']).resolve();assert q.is_relative_to(dest);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
 (dest/'metadata-only.json').write_bytes((root/'metadata-only.json').read_bytes())
if __name__=='__main__':main()
