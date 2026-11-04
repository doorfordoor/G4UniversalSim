# Vendored JSON parser: nlohmann/json 3.11.3

The F2 controlled-session protocol (roadmap item "backend session and replay")
needs a reliable, versioned JSON parser. The repository had none, so this fixed
release is vendored as a single header; there is no package manager or system
dependency involved.

| Field | Value |
| --- | --- |
| Project | JSON for Modern C++ (nlohmann/json) |
| Version | 3.11.3 |
| Upstream URL | https://github.com/nlohmann/json/releases/tag/v3.11.3 |
| Vendored file | `include/ThirdParty/SessionJsonDependency.hh` |
| Source URL | https://raw.githubusercontent.com/nlohmann/json/v3.11.3/single_include/nlohmann/json.hpp |
| SHA-256 | `9bea4c8066ef4a1c206b2be5a36302f8926f7fdc6087af5d20b417d0cf103ea6` |
| Size | 919,975 bytes |
| License | MIT (SPDX-License-Identifier: MIT) |

The header is part of the C++ source fingerprint (`include/**/*.hh`), so the
build identity records its exact bytes. Updating the release means replacing the
file, updating the hash in this document and in the capabilities `session`
section, and re-running the session protocol tests.

## License

MIT License

Copyright (c) 2013-2023 Niels Lohmann

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
