"""Exercise production geometry diagnostic sorting without Geant4 dependencies."""
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    compiler = shlex.split(os.environ["CXX"], posix=os.name != "nt") if os.environ.get("CXX") else []
    if not compiler:
        located = next((shutil.which(name) for name in ("g++", "clang++", "cl") if shutil.which(name)), None)
        assert located, "C++17 compiler required"
        compiler = [located]
    source = r'''
#include "Geometry/GeometryConfigDiagnostic.hh"
#include <iostream>
#include <stdexcept>
int main() {
 GeometryConfigDiagnostic a;
 a.code="unconsumed_key";a.category="schema";a.filename="geometry.ini";
 a.line=4;a.section="world";a.key="example";a.value="value";
 a.message="same message";a.suggestion="suggestion A";
 auto b=a;b.category="runtime";
 auto c=a;c.suggestion="suggestion B";
 auto d=a;d.line=5;
 std::vector<GeometryConfigDiagnostic> input{a,b,a,c,b,a,d,c,a};
 SortAndDeduplicateGeometryDiagnostics(input);
 if(input.size()!=4) throw std::runtime_error("duplicates lost identity or survived");
 SortAndDeduplicateGeometryDiagnostics(input);
 if(input.size()!=4) throw std::runtime_error("deduplication is not idempotent");
 unsigned schemaA=0,schemaB=0,runtime=0,otherLine=0;
 for(const auto& item:input) {
  if(item.line==5) ++otherLine;
  else if(item.category=="runtime") ++runtime;
  else if(item.suggestion=="suggestion A") ++schemaA;
  else if(item.suggestion=="suggestion B") ++schemaB;
 }
 if(schemaA!=1||schemaB!=1||runtime!=1||otherLine!=1)
   throw std::runtime_error("different diagnostic facts were collapsed");
 std::cout << input.size() << '\n';
}
'''
    with tempfile.TemporaryDirectory(prefix="g4usim-diagnostic-identity-") as directory:
        work = Path(directory)
        path = work / "diagnostics.cc"
        path.write_text(source, encoding="utf-8")
        executable = work / ("diagnostics.exe" if os.name == "nt" else "diagnostics")
        if Path(compiler[0]).stem.lower() in {"cl", "clang-cl"}:
            command = compiler + ["/nologo", "/std:c++17", "/EHsc", "/I" + str(root / "include"), str(path), "/Fe:" + str(executable)]
        else:
            command = compiler + ["-std=c++17", "-Wall", "-Wextra", "-pedantic", "-I", str(root / "include"), str(path), "-o", str(executable)]
        built = subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        result = subprocess.run([str(executable)], cwd=work, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == "4"
    print("Geometry diagnostic identity component passed")


if __name__ == "__main__":
    main()
