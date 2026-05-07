#ifndef G4UNIVERSALSIM_UTILS_FILE_UTILS_HH
#define G4UNIVERSALSIM_UTILS_FILE_UTILS_HH

#include <string>

namespace FileUtils {

bool Exists(const std::string& path);

bool IsFile(const std::string& path);

bool IsDirectory(const std::string& path);

void CreateDirectories(const std::string& path);

std::string CanonicalPath(const std::string& path);

std::string AbsolutePath(const std::string& path);

std::string JoinPath(const std::string& a, const std::string& b);

std::string ParentPath(const std::string& path);

std::string Filename(const std::string& path);

std::string Extension(const std::string& path);

std::string ReadTextFile(const std::string& path);

void WriteTextFile(const std::string& path, const std::string& content);

}  // namespace FileUtils

#endif  // G4UNIVERSALSIM_UTILS_FILE_UTILS_HH
