#ifndef G4UNIVERSALSIM_UTILS_STRING_UTILS_HH
#define G4UNIVERSALSIM_UTILS_STRING_UTILS_HH

#include <string>
#include <vector>

namespace StringUtils {

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
