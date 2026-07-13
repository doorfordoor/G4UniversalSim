#pragma once

#include <map>
#include <stdexcept>
#include <string>
#include <vector>

struct IniFieldInfo {
    std::string section;
    std::string key;
    std::string value;
    std::size_t lineNumber = 0;
        mutable bool consumed = false;
};

struct IniSectionInfo {
    std::string section;
    std::size_t lineNumber = 0;
    bool explicitSection = false;
};

class IniReader {
public:
    IniReader() = default;

    void Load(const std::string& filename);

    bool HasSection(const std::string& section) const;

    bool HasKey(const std::string& section, const std::string& key) const;

    std::string GetString(const std::string& section, const std::string& key) const;

    std::string GetString(
        const std::string& section,
        const std::string& key,
        const std::string& defaultValue
    ) const;

    std::vector<std::string> GetSections() const;

    std::vector<std::string> GetKeys(const std::string& section) const;

    std::vector<IniFieldInfo> GetFields() const;

    std::vector<IniSectionInfo> GetSectionInfo() const;

    const std::string& GetFilename() const;

    void Clear();

private:
    struct Entry {
        std::string value;
        std::size_t lineNumber = 0;
        std::string originalKey;
        mutable bool consumed = false;
    };

    using Section = std::map<std::string, Entry>;

    static std::string NormalizeName(const std::string& name);
    static std::runtime_error ParseError(
        const std::string& filename,
        std::size_t lineNumber,
        const std::string& message
    );

    std::string filename_;
    std::map<std::string, Section> data_;
    std::map<std::string, IniSectionInfo> sectionInfo_;
};
