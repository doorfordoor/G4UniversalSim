#include "Config/IniReader.hh"

#include "Utils/FileUtils.hh"
#include "Utils/StringUtils.hh"

#include <fstream>
#include <sstream>
#include <stdexcept>

namespace {

constexpr const char* kDefaultSection = "global";

}  // namespace

void IniReader::Load(const std::string& filename)
{
    Clear();

    if (!FileUtils::IsFile(filename)) {
        throw std::runtime_error("INI file does not exist: '" + filename + "'");
    }

    filename_ = filename;
    std::ifstream input(filename);
    if (!input) {
        throw std::runtime_error("Failed to open INI file: '" + filename + "'");
    }

    std::string currentSection = kDefaultSection;
    data_[currentSection];

    std::string line;
    std::size_t lineNumber = 0;
    while (std::getline(input, line)) {
        ++lineNumber;

        const std::string withoutComment =
            StringUtils::Trim(StringUtils::RemoveComment(line));
        if (withoutComment.empty()) {
            continue;
        }

        if (withoutComment.front() == '[') {
            if (withoutComment.back() != ']') {
                throw ParseError(filename, lineNumber, "missing closing ']'");
            }

            const std::string sectionName =
                StringUtils::Trim(withoutComment.substr(1, withoutComment.size() - 2));
            if (sectionName.empty()) {
                throw ParseError(filename, lineNumber, "empty section name");
            }

            currentSection = NormalizeName(sectionName);
            data_[currentSection];
            continue;
        }

        const auto equalPos = withoutComment.find('=');
        if (equalPos == std::string::npos) {
            throw ParseError(filename, lineNumber, "expected key = value");
        }

        const std::string key = StringUtils::Trim(withoutComment.substr(0, equalPos));
        const std::string value = StringUtils::Trim(withoutComment.substr(equalPos + 1));
        if (key.empty()) {
            throw ParseError(filename, lineNumber, "empty key");
        }

        data_[currentSection][NormalizeName(key)] = value;
    }

    if (input.bad()) {
        throw std::runtime_error("Failed while reading INI file: '" + filename + "'");
    }
}

bool IniReader::HasSection(const std::string& section) const
{
    return data_.find(NormalizeName(section)) != data_.end();
}

bool IniReader::HasKey(const std::string& section, const std::string& key) const
{
    const auto sectionIt = data_.find(NormalizeName(section));
    if (sectionIt == data_.end()) {
        return false;
    }
    return sectionIt->second.find(NormalizeName(key)) != sectionIt->second.end();
}

std::string IniReader::GetString(const std::string& section, const std::string& key) const
{
    const auto sectionName = NormalizeName(section);
    const auto keyName = NormalizeName(key);

    const auto sectionIt = data_.find(sectionName);
    if (sectionIt == data_.end()) {
        throw std::runtime_error(
            "Missing INI section '" + section + "' in file '" + filename_ + "'"
        );
    }

    const auto keyIt = sectionIt->second.find(keyName);
    if (keyIt == sectionIt->second.end()) {
        throw std::runtime_error(
            "Missing INI key '" + section + "/" + key + "' in file '" + filename_ + "'"
        );
    }

    return keyIt->second;
}

std::string IniReader::GetString(
    const std::string& section,
    const std::string& key,
    const std::string& defaultValue
) const
{
    if (!HasKey(section, key)) {
        return defaultValue;
    }
    return GetString(section, key);
}

std::vector<std::string> IniReader::GetSections() const
{
    std::vector<std::string> sections;
    for (const auto& item : data_) {
        sections.push_back(item.first);
    }
    return sections;
}

std::vector<std::string> IniReader::GetKeys(const std::string& section) const
{
    const auto sectionIt = data_.find(NormalizeName(section));
    if (sectionIt == data_.end()) {
        throw std::runtime_error(
            "Missing INI section '" + section + "' in file '" + filename_ + "'"
        );
    }

    std::vector<std::string> keys;
    for (const auto& item : sectionIt->second) {
        keys.push_back(item.first);
    }
    return keys;
}

const std::string& IniReader::GetFilename() const
{
    return filename_;
}

void IniReader::Clear()
{
    filename_.clear();
    data_.clear();
}

std::string IniReader::NormalizeName(const std::string& name)
{
    return StringUtils::ToLower(StringUtils::Trim(name));
}

std::runtime_error IniReader::ParseError(
    const std::string& filename,
    std::size_t lineNumber,
    const std::string& message
)
{
    std::ostringstream oss;
    oss << "INI parse error in '" << filename << "' at line "
        << lineNumber << ": " << message;
    return std::runtime_error(oss.str());
}
