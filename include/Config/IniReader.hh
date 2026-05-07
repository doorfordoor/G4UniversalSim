#pragma once

#include <map>
#include <stdexcept>
#include <string>
#include <vector>

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

    const std::string& GetFilename() const;

    void Clear();

private:
    using Section = std::map<std::string, std::string>;

    static std::string NormalizeName(const std::string& name);
    static std::runtime_error ParseError(
        const std::string& filename,
        std::size_t lineNumber,
        const std::string& message
    );

    std::string filename_;
    std::map<std::string, Section> data_;
};
