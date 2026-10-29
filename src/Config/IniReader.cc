#include "Config/IniReader.hh"

#include "Config/InputProvenance.hh"
#include "Utils/StringUtils.hh"

#include <fstream>
#include <sstream>
#include <stdexcept>

namespace {

constexpr const char* kDefaultSection = "global";

}  // namespace

void IniReader::Load(const std::string& filename)
{
    const auto input = input_provenance::ReadFile(filename);
    LoadBytes(filename, input.bytes);
}

void IniReader::LoadBytes(const std::string& filename, const std::string& bytes)
{
    IniReader candidate;
    candidate.ParseBytes(filename, bytes);
    candidate.inputSha256_ = input_provenance::Sha256(bytes);
    // All allocations/parse validation complete before replacing accepted state.
    using std::swap;
    swap(*this, candidate);
}

void IniReader::ParseBytes(const std::string& filename, const std::string& bytes)
{
    filename_ = filename;
    std::istringstream input(bytes);
    // Loading a second file into the same reader replaces the parsed data; drop the bookkeeping
    // of the previous file so duplicate reports never mix two files.
    duplicates_.clear();
    sectionFirstLine_.clear();
    keyFirstLine_.clear();

    std::string currentSection = kDefaultSection;
    std::string currentOriginalSection = kDefaultSection;
    data_[currentSection];
    sectionInfo_[currentSection] = {currentSection, 0, false, currentOriginalSection, currentSection};

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

            currentOriginalSection = sectionName;
            currentSection = NormalizeName(sectionName);
            data_[currentSection];
            const auto seenSection = sectionFirstLine_.find(currentSection);
            if (seenSection != sectionFirstLine_.end()) {
                duplicates_.push_back({currentSection, "", seenSection->second, lineNumber});
            } else {
                sectionFirstLine_[currentSection] = lineNumber;
            }
            sectionInfo_[currentSection] = {currentSection, lineNumber, true, currentOriginalSection, currentSection};
            sectionDeclarations_.push_back(sectionInfo_[currentSection]);
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

        const std::string normalizedKey = NormalizeName(key);
        const auto seenKey = keyFirstLine_[currentSection].find(normalizedKey);
        if (seenKey != keyFirstLine_[currentSection].end()) {
            duplicates_.push_back({currentSection, normalizedKey, seenKey->second, lineNumber});
        } else {
            keyFirstLine_[currentSection][normalizedKey] = lineNumber;
        }
        data_[currentSection][normalizedKey] = {value, lineNumber, currentOriginalSection, key};
        declarations_.push_back({currentSection, key, value, lineNumber, false,
                                 currentOriginalSection, currentSection, key, normalizedKey, line});
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

    keyIt->second.consumed = true;
    return keyIt->second.value;
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

std::vector<IniFieldInfo> IniReader::GetFields() const
{
    std::vector<IniFieldInfo> fields;
    for (const auto& section : data_) {
        for (const auto& item : section.second) {
            fields.push_back({section.first, item.second.originalKey, item.second.value,
                              item.second.lineNumber, item.second.consumed,
                              item.second.originalSection, section.first,
                              item.second.originalKey, NormalizeName(item.second.originalKey)});
        }
    }
    return fields;
}

std::vector<IniDuplicateInfo> IniReader::GetDuplicates() const
{
    return duplicates_;
}

std::vector<IniSectionInfo> IniReader::GetSectionInfo() const
{
    std::vector<IniSectionInfo> sections;
    for (const auto& item : sectionInfo_) sections.push_back(item.second);
    return sections;
}

const std::string& IniReader::GetFilename() const
{
    return filename_;
}

std::vector<IniFieldInfo> IniReader::GetDeclarations() const
{
    auto result = declarations_;
    for (auto& field : result) {
        const auto section = data_.find(field.normalizedSection);
        if (section != data_.end()) {
            const auto key = section->second.find(field.normalizedKey);
            if (key != section->second.end() && key->second.lineNumber == field.lineNumber)
                field.consumed = key->second.consumed;
        }
    }
    return result;
}

void IniReader::Clear()
{
    inputSha256_.clear();
    declarations_.clear();
    sectionDeclarations_.clear();
    filename_.clear();
    data_.clear();
    sectionInfo_.clear();
    duplicates_.clear();
    sectionFirstLine_.clear();
    keyFirstLine_.clear();
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
