#include "Utils/StringUtils.hh"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <stdexcept>

namespace {

bool IsSpace(unsigned char c)
{
    return std::isspace(c) != 0;
}

}  // namespace

namespace StringUtils {

std::string LTrim(const std::string& s)
{
    auto first = std::find_if_not(s.begin(), s.end(), [](unsigned char c) {
        return IsSpace(c);
    });
    return std::string(first, s.end());
}

std::string RTrim(const std::string& s)
{
    auto last = std::find_if_not(s.rbegin(), s.rend(), [](unsigned char c) {
        return IsSpace(c);
    });
    return std::string(s.begin(), last.base());
}

std::string Trim(const std::string& s)
{
    return RTrim(LTrim(s));
}

std::vector<std::string> Split(
    const std::string& s,
    char delimiter,
    bool skipEmpty
)
{
    std::vector<std::string> result;
    std::string item;
    std::stringstream ss(s);

    while (std::getline(ss, item, delimiter)) {
        if (!skipEmpty || !item.empty()) {
            result.push_back(item);
        }
    }

    if (!skipEmpty && !s.empty() && s.back() == delimiter) {
        result.emplace_back();
    }

    return result;
}

std::vector<std::string> SplitWhitespace(const std::string& s)
{
    std::vector<std::string> result;
    std::istringstream iss(s);
    std::string item;

    while (iss >> item) {
        result.push_back(item);
    }

    return result;
}

std::string ToLower(const std::string& s)
{
    std::string result = s;
    std::transform(result.begin(), result.end(), result.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return result;
}

std::string ToUpper(const std::string& s)
{
    std::string result = s;
    std::transform(result.begin(), result.end(), result.begin(), [](unsigned char c) {
        return static_cast<char>(std::toupper(c));
    });
    return result;
}

bool StartsWith(const std::string& s, const std::string& prefix)
{
    return prefix.size() <= s.size()
        && std::equal(prefix.begin(), prefix.end(), s.begin());
}

bool EndsWith(const std::string& s, const std::string& suffix)
{
    return suffix.size() <= s.size()
        && std::equal(suffix.rbegin(), suffix.rend(), s.rbegin());
}

bool Contains(const std::string& s, const std::string& token)
{
    return s.find(token) != std::string::npos;
}

std::string RemoveComment(
    const std::string& s,
    const std::vector<char>& commentChars
)
{
    std::string::size_type pos = std::string::npos;

    for (char commentChar : commentChars) {
        const auto current = s.find(commentChar);
        if (current != std::string::npos) {
            pos = (pos == std::string::npos) ? current : std::min(pos, current);
        }
    }

    return pos == std::string::npos ? s : s.substr(0, pos);
}

bool ToBool(const std::string& s)
{
    const std::string value = ToLower(Trim(s));

    if (value == "true" || value == "yes" || value == "on" || value == "1") {
        return true;
    }

    if (value == "false" || value == "no" || value == "off" || value == "0") {
        return false;
    }

    throw std::runtime_error("Cannot parse boolean value: '" + s + "'");
}

std::string Join(
    const std::vector<std::string>& items,
    const std::string& delimiter
)
{
    std::ostringstream oss;
    for (std::size_t i = 0; i < items.size(); ++i) {
        if (i != 0) {
            oss << delimiter;
        }
        oss << items[i];
    }
    return oss.str();
}

}  // namespace StringUtils
