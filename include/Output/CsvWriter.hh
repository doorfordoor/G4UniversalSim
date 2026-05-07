#pragma once

#include <fstream>
#include <initializer_list>
#include <string>
#include <vector>

class CsvWriter {
public:
    CsvWriter() = default;
    explicit CsvWriter(const std::string& filename);
    ~CsvWriter() noexcept;

    void Open(const std::string& filename);
    bool IsOpen() const;

    void WriteHeader(const std::vector<std::string>& columns);

    void WriteRow(const std::vector<std::string>& values);
    void WriteRow(std::initializer_list<std::string> values);
    void WriteRow(const std::vector<double>& values);
    void WriteRow(const std::vector<int>& values);

    void Flush();
    void Close();

    void SetPrecision(int precision);
    int GetPrecision() const;

    const std::string& GetFilename() const;

private:
    std::string Escape(const std::string& value) const;
    void WriteEscapedRow(const std::vector<std::string>& values);
    void CheckColumnCount(const std::vector<std::string>& values) const;

    std::ofstream stream_;
    std::string filename_;
    std::size_t columnCount_ = 0;
    bool headerWritten_ = false;
    int precision_ = 12;
};
