#ifndef G4UNIVERSALSIM_UTILS_STRING_UTILS_HH
#define G4UNIVERSALSIM_UTILS_STRING_UTILS_HH

#include <string>
#include <vector>

namespace StringUtils {

// Geant4 collapses repeated slashes in command paths before dispatch. Apply
// that same normalization to guards, without rewriting any parameter/path.
inline std::string NormalizeCommandSlashes(const std::string& line)
{
    std::string result;
    bool arguments = false;
    for (char ch : line) {
        if (ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n') arguments = true;
        if (!arguments && ch == '/' && !result.empty() && result.back() == '/') continue;
        result.push_back(ch);
    }
    return result;
}

std::string Trim(const std::string& s);

std::string LTrim(const std::string& s);

std::string RTrim(const std::string& s);

std::vector<std::string> Split(
    const std::string& s,
    char delimiter,
    bool skipEmpty = true
);

std::vector<std::string> SplitWhitespace(const std::string& s);

std::string ToLower(const std::string& s);

std::string ToUpper(const std::string& s);

bool StartsWith(const std::string& s, const std::string& prefix);

bool EndsWith(const std::string& s, const std::string& suffix);

bool Contains(const std::string& s, const std::string& token);

std::string RemoveComment(
    const std::string& s,
    const std::vector<char>& commentChars = {'#', ';'}
);

bool ToBool(const std::string& s);

std::string Join(
    const std::vector<std::string>& items,
    const std::string& delimiter
);

}  // namespace StringUtils

#endif  // G4UNIVERSALSIM_UTILS_STRING_UTILS_HH
