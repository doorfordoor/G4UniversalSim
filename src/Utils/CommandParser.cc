#include "Utils/CommandParser.hh"

#include "Utils/StringUtils.hh"

#include <cctype>
#include <cstdlib>
#include <stdexcept>

namespace {

std::string FormatExamples(const std::string& examples)
{
    return examples.empty() ? std::string() : " Supported formats: " + examples;
}

bool LooksLikeKeyValueStart(const std::string& token)
{
    const auto pos = token.find('=');
    return pos != std::string::npos && pos > 0;
}

std::string NormalizeKey(const std::string& key)
{
    return StringUtils::ToLower(StringUtils::Trim(key));
}

}  // namespace

namespace CommandParser {

std::vector<std::string> SplitWhitespaceRespectQuotes(const std::string& text)
{
    std::vector<std::string> tokens;
    std::string current;
    bool inQuotes = false;

    for (char ch : text) {
        if (ch == '"') {
            inQuotes = !inQuotes;
            continue;
        }
        if (std::isspace(static_cast<unsigned char>(ch)) && !inQuotes) {
            if (!current.empty()) {
                tokens.push_back(current);
                current.clear();
            }
        } else {
            current.push_back(ch);
        }
    }

    if (inQuotes) {
        throw std::runtime_error("unclosed quote in command input");
    }
    if (!current.empty()) {
        tokens.push_back(current);
    }
    return tokens;
}

std::map<std::string, std::string> ParseKeyValueLine(
    const std::string& line,
    const std::string& examples
)
{
    std::map<std::string, std::string> values;
    const auto tokens = SplitWhitespaceRespectQuotes(line);

    std::string currentKey;
    for (std::size_t i = 0; i < tokens.size(); ++i) {
        const std::string token = StringUtils::Trim(tokens[i]);
        if (token.empty()) {
            continue;
        }

        const auto pos = token.find('=');
        if (pos != std::string::npos) {
            if (pos == 0) {
                throw std::runtime_error(
                    "empty key in token '" + token + "'." + FormatExamples(examples));
            }

            currentKey = NormalizeKey(token.substr(0, pos));
            if (currentKey.empty()) {
                throw std::runtime_error(
                    "empty key in token '" + token + "'." + FormatExamples(examples));
            }

            values[currentKey] = StringUtils::Trim(token.substr(pos + 1));
            continue;
        }

        if (token == "=") {
            throw std::runtime_error(
                "standalone '=' is not supported; use key=value." + FormatExamples(examples));
        }

        if (currentKey.empty()) {
            throw std::runtime_error(
                "expected key=value token, got '" + token + "'." + FormatExamples(examples));
        }

        if (LooksLikeKeyValueStart(token)) {
            throw std::runtime_error(
                "internal parser error near token '" + token + "'." + FormatExamples(examples));
        }

        if (!values[currentKey].empty()) {
            values[currentKey] += " ";
        }
        values[currentKey] += token;
    }

    return values;
}

std::string RequiredValue(
    const std::map<std::string, std::string>& values,
    const std::string& key,
    const std::string& context
)
{
    const auto normalizedKey = NormalizeKey(key);
    const auto it = values.find(normalizedKey);
    if (it == values.end() || StringUtils::Trim(it->second).empty()) {
        const std::string prefix = context.empty() ? std::string() : context + ": ";
        throw std::runtime_error(prefix + "missing required key '" + key + "'");
    }
    return it->second;
}

std::string OptionalValue(
    const std::map<std::string, std::string>& values,
    const std::string& key,
    const std::string& defaultValue
)
{
    const auto it = values.find(NormalizeKey(key));
    return it == values.end() ? defaultValue : it->second;
}

bool OptionalBool(
    const std::map<std::string, std::string>& values,
    const std::string& key,
    bool defaultValue
)
{
    const auto it = values.find(NormalizeKey(key));
    return it == values.end() ? defaultValue : StringUtils::ToBool(it->second);
}

int ParseInt(const std::string& text, const std::string& key)
{
    const std::string trimmed = StringUtils::Trim(text);
    if (trimmed.empty()) {
        throw std::runtime_error("empty integer value" + (key.empty() ? std::string() : " for key '" + key + "'"));
    }

    std::size_t consumed = 0;
    int value = 0;
    try {
        value = std::stoi(trimmed, &consumed);
    } catch (const std::exception&) {
        throw std::runtime_error("invalid integer value '" + text + "'" + (key.empty() ? std::string() : " for key '" + key + "'"));
    }

    if (consumed != trimmed.size()) {
        throw std::runtime_error("invalid trailing text in integer value '" + text + "'" + (key.empty() ? std::string() : " for key '" + key + "'"));
    }
    return value;
}

double ParseDouble(const std::string& text, const std::string& key)
{
    const std::string trimmed = StringUtils::Trim(text);
    if (trimmed.empty()) {
        throw std::runtime_error("empty numeric value" + (key.empty() ? std::string() : " for key '" + key + "'"));
    }

    char* end = nullptr;
    const double value = std::strtod(trimmed.c_str(), &end);
    if (end == trimmed.c_str()) {
        throw std::runtime_error("invalid numeric value '" + text + "'" + (key.empty() ? std::string() : " for key '" + key + "'"));
    }

    const std::string tail = StringUtils::Trim(std::string(end));
    if (!tail.empty()) {
        throw std::runtime_error("invalid trailing text in numeric value '" + text + "'" + (key.empty() ? std::string() : " for key '" + key + "'"));
    }
    return value;
}

}  // namespace CommandParser
