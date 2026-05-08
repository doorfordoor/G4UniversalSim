#pragma once

#include <map>
#include <string>
#include <vector>

namespace CommandParser {

std::vector<std::string> SplitWhitespaceRespectQuotes(const std::string& text);

std::map<std::string, std::string> ParseKeyValueLine(
    const std::string& line,
    const std::string& examples = ""
);

std::string RequiredValue(
    const std::map<std::string, std::string>& values,
    const std::string& key,
    const std::string& context = ""
);

std::string OptionalValue(
    const std::map<std::string, std::string>& values,
    const std::string& key,
    const std::string& defaultValue
);

bool OptionalBool(
    const std::map<std::string, std::string>& values,
    const std::string& key,
    bool defaultValue
);

int ParseInt(const std::string& text, const std::string& key = "");

double ParseDouble(const std::string& text, const std::string& key = "");

}  // namespace CommandParser
