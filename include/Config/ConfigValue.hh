#pragma once

#include <string>
#include <vector>

class ConfigValue {
public:
    ConfigValue() = default;

    explicit ConfigValue(const std::string& value);

    const std::string& AsString() const;

    int AsInt() const;

    double AsDouble() const;

    bool AsBool() const;

    std::vector<std::string> AsStringVector(char delimiter = ',') const;

    std::vector<int> AsIntVector(char delimiter = ',') const;

    std::vector<double> AsDoubleVector(char delimiter = ',') const;

    bool Empty() const;

private:
    std::string value_;
};
