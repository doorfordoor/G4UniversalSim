#ifndef G4UNIVERSALSIM_UTILS_UNIT_PARSER_HH
#define G4UNIVERSALSIM_UTILS_UNIT_PARSER_HH

#include <string>
#include <vector>

namespace UnitParser {

double ParseDouble(const std::string& text);

double ParseDoubleWithUnit(const std::string& text);

double ParseLength(const std::string& text);

double ParseEnergy(const std::string& text);

double ParseTime(const std::string& text);

double ParseAngle(const std::string& text);

std::vector<double> ParseVectorDouble(
    const std::string& text,
    char delimiter = ','
);

std::vector<double> ParseVectorWithUnit(
    const std::string& text,
    char delimiter = ','
);

}  // namespace UnitParser

#endif  // G4UNIVERSALSIM_UTILS_UNIT_PARSER_HH
