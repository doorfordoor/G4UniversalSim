#include "Utils/NamedParameters.hh"
#include "Utils/StringUtils.hh"
#include "Utils/UnitParser.hh"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <functional>
#include <stdexcept>

namespace named_parameters {
namespace {
using Lookup = std::function<const Expansion&(const std::string&)>;
bool Alpha(char c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'); }
bool Digit(char c) { return c >= '0' && c <= '9'; }
void Require(bool ok, const std::string& detail) {
    if (!ok) throw std::runtime_error(detail);
}
class Parser {
public:
    Parser(const std::string& text, const Lookup& lookup, Dimension domain) : text_(text), lookup_(lookup), domain_(domain) {}
    Expansion Run() {
        Require(text_.size() <= 4096, "expression exceeds 4096 bytes");
        auto value = Sum(0);
        Require(Peek() == 0 && pos_ == text_.size(), "unexpected trailing expression input");
        return {value, dependencies_};
    }
private:
    char Peek() {
        while (pos_ < text_.size() && (text_[pos_] == ' ' || text_[pos_] == '\t')) ++pos_;
        return pos_ == text_.size() ? 0 : text_[pos_];
    }
    Quantity Sum(unsigned depth) {
        auto a = Product(depth);
        while (Peek() == '+' || Peek() == '-') {
            const char op = text_[pos_++];
            auto b = Product(depth);
            Require(a.dimension == b.dimension, "addition/subtraction dimension mismatch");
            a.value += op == '+' ? b.value : -b.value;
            Require(std::isfinite(a.value), "non-finite expression result");
        }
        return a;
    }
    Quantity Product(unsigned depth) {
        auto a = Atom(depth);
        while (Peek() == '*' || Peek() == '/') {
            const char op = text_[pos_++];
            auto b = Atom(depth);
            if (op == '*') {
                Require(a.dimension == Dimension::Scalar || b.dimension == Dimension::Scalar, "unsupported product dimension");
                a = {a.value*b.value, a.dimension == Dimension::Scalar ? b.dimension : a.dimension};
            } else {
                Require(b.value != 0., "division by zero");
                Require(b.dimension == Dimension::Scalar || a.dimension == b.dimension, "unsupported quotient dimension");
                a = {a.value/b.value, b.dimension == Dimension::Scalar ? a.dimension : Dimension::Scalar};
            }
            Require(std::isfinite(a.value), "non-finite expression result");
        }
        return a;
    }
    Quantity Atom(unsigned depth) {
        Require(depth < 64, "expression nesting exceeds 64");
        const char c = Peek();
        if (c == '+' || c == '-') {
            ++pos_;
            auto a = Atom(depth+1);
            if (c == '-') a.value = -a.value;
            return a;
        }
        if (c == '(') {
            ++pos_;
            auto a = Sum(depth+1);
            Require(Peek() == ')', "expected closing parenthesis");
            ++pos_;
            return a;
        }
        if (text_.compare(pos_, 2, "${") == 0) {
            const auto end = text_.find('}', pos_+2);
            Require(end != std::string::npos, "unterminated parameter reference");
            const auto name = StringUtils::ToLower(text_.substr(pos_+2, end-pos_-2));
            Require(Table::ValidName(name), "invalid parameter reference");
            pos_ = end+1;
            const auto& value = lookup_(name);
            dependencies_.insert(name);
            dependencies_.insert(value.dependencies.begin(), value.dependencies.end());
            return value.quantity;
        }
        Require(Digit(c) || c == '.', "expected number or parameter reference");
        const auto begin = pos_;
        char* end = nullptr;
        std::strtod(text_.c_str()+pos_, &end);
        pos_ = static_cast<std::size_t>(end-text_.c_str());
        Require(pos_ > begin, "invalid numeric literal");
        const auto number = text_.substr(begin,pos_-begin);
        Peek();
        const auto unitBegin = pos_;
        while (pos_ < text_.size() && Alpha(text_[pos_])) ++pos_;
        if (unitBegin == pos_) return {UnitParser::ParseDouble(number), Dimension::Scalar};
        const auto literal = number+" "+text_.substr(unitBegin,pos_-unitBegin);
        const double value = domain_ == Dimension::Energy ? UnitParser::ParseEnergy(literal) : UnitParser::ParseLength(literal);
        Require(std::isfinite(value), "non-finite quantity literal");
        return {value,domain_};
    }
    const std::string& text_;
    const Lookup& lookup_;
    Dimension domain_;
    std::size_t pos_ = 0;
    std::set<std::string> dependencies_;
};
}

bool Table::ValidName(const std::string& name) {
    if (name.empty() || name.size()>64 || !(Alpha(name.front()) || name.front()=='_')) return false;
    for (char c:name) if (!(Alpha(c) || Digit(c) || c=='_')) return false;
    return true;
}

Table::Table(const std::map<std::string, Definition>& definitions, Dimension domain) : domain_(domain) {
    Require(domain == Dimension::Length || domain == Dimension::Energy, "expected length or energy table");
    Require(definitions.size()<=256, "parameter count exceeds 256");
    std::set<std::string> visiting;
    std::map<std::string, unsigned> depths;
    Lookup resolve = [&](const std::string& name) -> const Expansion& {
        const auto done = values_.find(name);
        if (done != values_.end()) return done->second;
        const auto it = definitions.find(name);
        Require(it != definitions.end(), "undefined parameter '"+name+"'");
        Require(visiting.insert(name).second, "cyclic parameter '"+name+"'");
        Require(visiting.size()<=32, "parameter dependency nesting exceeds 32");
        try {
            auto result = Parser(it->second.expression,resolve,domain_).Run();
            unsigned depth = 1;
            for (const auto& dependency : result.dependencies)
                depth = std::max(depth, 1 + depths.at(dependency));
            Require(depth <= 32, "parameter dependency nesting exceeds 32");
            depths.emplace(name, depth);
            visiting.erase(name);
            return values_.emplace(name,std::move(result)).first->second;
        } catch (const std::exception& e) {
            throw std::runtime_error(it->second.location+": "+e.what());
        }
    };
    for (const auto& definition:definitions) resolve(definition.first);
}

Expansion Table::Evaluate(const std::string& expression) const {
    Lookup lookup = [&](const std::string& name) -> const Expansion& {
        const auto it = values_.find(name);
        Require(it != values_.end(),"undefined parameter '"+name+"'");
        return it->second;
    };
    return Parser(expression,lookup,domain_).Run();
}
}
