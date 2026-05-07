#include "Output/CsvWriter.hh"

#include "Utils/FileUtils.hh"

#include <iomanip>
#include <sstream>
#include <stdexcept>

CsvWriter::CsvWriter(const std::string& filename)
{
    Open(filename);
}

CsvWriter::~CsvWriter() noexcept
{
    try {
        Close();
    } catch (...) {
    }
}

void CsvWriter::Open(const std::string& filename)
{
    Close();

    const std::string parent = FileUtils::ParentPath(filename);
    if (!parent.empty()) {
        FileUtils::CreateDirectories(parent);
    }

    stream_.open(filename);
    if (!stream_) {
        throw std::runtime_error("Failed to open CSV file for writing: '" + filename + "'");
    }

    filename_ = filename;
    columnCount_ = 0;
    headerWritten_ = false;
}

bool CsvWriter::IsOpen() const
{
    return stream_.is_open();
}

void CsvWriter::WriteHeader(const std::vector<std::string>& columns)
{
    if (!IsOpen()) {
        throw std::runtime_error("Cannot write CSV header; file is not open: '" + filename_ + "'");
    }
    if (headerWritten_) {
        throw std::runtime_error("CSV header already written for file: '" + filename_ + "'");
    }

    columnCount_ = columns.size();
    WriteEscapedRow(columns);
    headerWritten_ = true;
}

void CsvWriter::WriteRow(const std::vector<std::string>& values)
{
    if (!IsOpen()) {
        throw std::runtime_error("Cannot write CSV row; file is not open: '" + filename_ + "'");
    }
    CheckColumnCount(values);
    WriteEscapedRow(values);
}

void CsvWriter::WriteRow(std::initializer_list<std::string> values)
{
    WriteRow(std::vector<std::string>(values));
}

void CsvWriter::WriteRow(const std::vector<double>& values)
{
    std::vector<std::string> converted;
    converted.reserve(values.size());

    for (double value : values) {
        std::ostringstream oss;
        oss << std::setprecision(precision_) << value;
        converted.push_back(oss.str());
    }

    WriteRow(converted);
}

void CsvWriter::WriteRow(const std::vector<int>& values)
{
    std::vector<std::string> converted;
    converted.reserve(values.size());

    for (int value : values) {
        converted.push_back(std::to_string(value));
    }

    WriteRow(converted);
}

void CsvWriter::Flush()
{
    if (IsOpen()) {
        stream_.flush();
        if (!stream_) {
            throw std::runtime_error("Failed to flush CSV file: '" + filename_ + "'");
        }
    }
}

void CsvWriter::Close()
{
    if (stream_.is_open()) {
        stream_.flush();
        stream_.close();
    }
}

void CsvWriter::SetPrecision(int precision)
{
    if (precision <= 0) {
        throw std::runtime_error("CSV precision must be positive");
    }
    precision_ = precision;
}

int CsvWriter::GetPrecision() const
{
    return precision_;
}

const std::string& CsvWriter::GetFilename() const
{
    return filename_;
}

std::string CsvWriter::Escape(const std::string& value) const
{
    const bool needsQuotes = value.find_first_of(",\"\r\n") != std::string::npos;
    if (!needsQuotes) {
        return value;
    }

    std::string escaped;
    escaped.reserve(value.size() + 2);
    escaped.push_back('"');
    for (char c : value) {
        if (c == '"') {
            escaped += "\"\"";
        } else {
            escaped.push_back(c);
        }
    }
    escaped.push_back('"');
    return escaped;
}

void CsvWriter::WriteEscapedRow(const std::vector<std::string>& values)
{
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i != 0) {
            stream_ << ',';
        }
        stream_ << Escape(values[i]);
    }
    stream_ << '\n';

    if (!stream_) {
        throw std::runtime_error("Failed to write CSV file: '" + filename_ + "'");
    }
}

void CsvWriter::CheckColumnCount(const std::vector<std::string>& values) const
{
    if (headerWritten_ && values.size() != columnCount_) {
        throw std::runtime_error(
            "CSV column count mismatch for file '" + filename_ + "': expected "
            + std::to_string(columnCount_) + ", got " + std::to_string(values.size())
        );
    }
}
