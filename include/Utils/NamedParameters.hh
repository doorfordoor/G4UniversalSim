#pragma once

#include <map>
#include <set>
#include <string>

namespace named_parameters {
enum class Dimension { Scalar, Length, Energy };
struct Quantity {
    double value;
    Dimension dimension;
    bool IsLength() const { return dimension == Dimension::Length; }
};
struct Definition {
    std::string expression;
    std::string location;
};
struct Expansion {
    Quantity quantity;
    std::set<std::string> dependencies;
};
class Table {
public:
    explicit Table(const std::map<std::string, Definition>& definitions, Dimension domain = Dimension::Length);
    Expansion Evaluate(const std::string& expression) const;
    const std::map<std::string, Expansion>& Values() const { return values_; }
    static bool ValidName(const std::string& name);
private:
    Dimension domain_;
    std::map<std::string, Expansion> values_;
};
}
