#include "Output/RunSummary.hh"

#include "Output/CsvWriter.hh"
#include "Utils/FileUtils.hh"

#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>

void RunSummary::Set(const std::string& key, const std::string& value)
{
    values_[key] = value;
}

void RunSummary::Set(const std::string& key, int value)
{
    values_[key] = std::to_string(value);
}

void RunSummary::Set(const std::string& key, double value)
{
    std::ostringstream oss;
    oss << std::setprecision(12) << value;
    values_[key] = oss.str();
}

void RunSummary::SetBool(const std::string& key, bool value)
{
    values_[key] = value ? "true" : "false";
}

bool RunSummary::Has(const std::string& key) const
{
    return values_.find(key) != values_.end();
}

std::string RunSummary::Get(const std::string& key, const std::string& defaultValue) const
{
    const auto it = values_.find(key);
    return it == values_.end() ? defaultValue : it->second;
}

void RunSummary::AddMessage(const std::string& message)
{
    messages_.push_back(message);
}

void RunSummary::AddWarning(const std::string& warning)
{
    warnings_.push_back(warning);
}

void RunSummary::WriteText(const std::string& filename) const
{
    const std::string parent = FileUtils::ParentPath(filename);
    if (!parent.empty()) {
        FileUtils::CreateDirectories(parent);
    }

    std::ofstream out(filename);
    if (!out) {
        throw std::runtime_error("Failed to open run summary file: '" + filename + "'");
    }

    out << "Run Summary\n";
    out << "===========\n\n";

    out << "[Values]\n";
    for (const auto& item : values_) {
        out << item.first << " = " << item.second << '\n';
    }

    out << "\n[Messages]\n";
    for (const std::string& message : messages_) {
        out << "- " << message << '\n';
    }

    out << "\n[Warnings]\n";
    for (const std::string& warning : warnings_) {
        out << "- " << warning << '\n';
    }

    if (!out) {
        throw std::runtime_error("Failed to write run summary file: '" + filename + "'");
    }
}

void RunSummary::WriteCSV(const std::string& filename) const
{
    CsvWriter writer(filename);
    writer.WriteHeader({"type", "key", "value"});

    for (const auto& item : values_) {
        writer.WriteRow({"value", item.first, item.second});
    }
    for (const std::string& message : messages_) {
        writer.WriteRow({"message", "", message});
    }
    for (const std::string& warning : warnings_) {
        writer.WriteRow({"warning", "", warning});
    }
}

void RunSummary::Clear()
{
    values_.clear();
    messages_.clear();
    warnings_.clear();
}
