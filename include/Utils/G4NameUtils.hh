#ifndef G4UNIVERSALSIM_UTILS_G4_NAME_UTILS_HH
#define G4UNIVERSALSIM_UTILS_G4_NAME_UTILS_HH

#include <string>

namespace G4NameUtils {

std::string SanitizeName(const std::string& raw);

std::string MakeUniqueName(const std::string& base, int index);

std::string LogicalName(const std::string& base);

std::string PhysicalName(const std::string& base);

std::string SolidName(const std::string& base);

std::string RegionName(const std::string& base);

}  // namespace G4NameUtils

#endif  // G4UNIVERSALSIM_UTILS_G4_NAME_UTILS_HH
