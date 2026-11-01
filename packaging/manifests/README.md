# Reviewed installation catalogs

No prebuilt release URL or SHA256 is asserted by this directory. Generate a local
catalog with `packaging/build_install_catalog.py` only after assembling and
reviewing an actual archive. The catalog records the archive hash, byte size,
per-file hashes, bundled license text and its source, exact platform, architecture,
version and profile. It is usable offline, including on systems without Qt or a
compiler. A catalog's `reviewed: true` is a publisher declaration, not a signature.

Runtime packages contain their runtime dependencies and do not require a compiler.
SDK catalogs must list required `compiler` and `cmake` dependencies. Installing SDK
files does not establish that a compiler works; a real SDK compile probe is separate.
Existing I1 environment facts may be attached to plans, but are never upgraded into
newly observed installation or runtime evidence.
