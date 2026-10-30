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
    std::string originalSection;
    std::string normalizedSection;
    std::string originalKey;
    std::string normalizedKey;
    std::string rawLine; // exact line content excluding LF, retains comments/spacing/CR
};

// A repeated [section] header or repeated key inside one section. The parser keeps its
// historical last-value-wins behavior, but records every repetition so callers can report
// it instead of silently dropping the earlier declaration.
struct IniDuplicateInfo {
    std::string section;      // normalized section name
    std::string key;          // normalized key; empty for a repeated section header
    std::size_t firstLine = 0;
    std::size_t lineNumber = 0;  // line of the repeated declaration
};

struct IniSectionInfo {
    std::string section;
    std::size_t lineNumber = 0;
    bool explicitSection = false;
    std::string originalSection;
    std::string normalizedSection;
};

class IniReader {
public:
    IniReader() = default;

    void Load(const std::string& filename, const std::string& kind = "ini");
    void LoadBytes(const std::string& filename, const std::string& bytes);

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

    std::vector<IniDuplicateInfo> GetDuplicates() const;

    const std::string& GetFilename() const;

    // Full source order, including overridden declarations; no consumption side effects.
    std::vector<IniFieldInfo> GetDeclarations() const;
    std::vector<IniSectionInfo> GetSectionDeclarations() const { return sectionDeclarations_; }
    const std::string& GetInputSha256() const { return inputSha256_; }
    void Clear();

private:
    struct Entry {
        std::string value;
        std::size_t lineNumber = 0;
        std::string originalSection;
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

    void ParseBytes(const std::string& filename, const std::string& bytes);
    std::string inputSha256_;
    std::vector<IniFieldInfo> declarations_;
    std::vector<IniSectionInfo> sectionDeclarations_;
    std::string filename_;
    std::map<std::string, Section> data_;
    std::map<std::string, IniSectionInfo> sectionInfo_;
    std::vector<IniDuplicateInfo> duplicates_;
    std::map<std::string, std::size_t> sectionFirstLine_;
    std::map<std::string, std::map<std::string, std::size_t>> keyFirstLine_;
};
