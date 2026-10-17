#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

struct Options {
  fs::path inputDir;
  std::string pattern;
  fs::path output;
  std::vector<fs::path> files;
};

struct Bin {
  double low = 0.0;
  double high = 0.0;
  std::vector<double> values;
};

std::vector<std::string> SplitCsvLine(const std::string& line) {
  std::vector<std::string> values;
  std::string current;
  bool inQuotes = false;
  for (char ch : line) {
    if (ch == '"') {
      inQuotes = !inQuotes;
      continue;
    }
    if (ch == ',' && !inQuotes) {
      values.push_back(current);
      current.clear();
    } else {
      current.push_back(ch);
    }
  }
  values.push_back(current);
  return values;
}

std::string Trim(const std::string& text) {
  const auto first = text.find_first_not_of(" \t\r\n");
  if (first == std::string::npos) return "";
  const auto last = text.find_last_not_of(" \t\r\n");
  return text.substr(first, last - first + 1);
}

bool IsNumber(const std::string& text) {
  char* end = nullptr;
  const auto trimmed = Trim(text);
  if (trimmed.empty()) return false;
  std::strtod(trimmed.c_str(), &end);
  return end != trimmed.c_str() && Trim(std::string(end)).empty();
}

double ToDouble(const std::string& text, const fs::path& file, int lineNumber) {
  const auto trimmed = Trim(text);
  char* end = nullptr;
  const double value = std::strtod(trimmed.c_str(), &end);
  if (end == trimmed.c_str() || !Trim(std::string(end)).empty() ||
      !std::isfinite(value)) {
    throw std::runtime_error(file.string() + ":" + std::to_string(lineNumber) +
                             ": expected numeric CSV field, got '" + text +
                             "'");
  }
  return value;
}

bool WildcardMatch(const std::string& pattern, const std::string& text) {
  std::size_t p = 0, t = 0, star = std::string::npos, match = 0;
  while (t < text.size()) {
    if (p < pattern.size() && (pattern[p] == '?' || pattern[p] == text[t])) {
      ++p;
      ++t;
    } else if (p < pattern.size() && pattern[p] == '*') {
      star = p++;
      match = t;
    } else if (star != std::string::npos) {
      p = star + 1;
      t = ++match;
    } else {
      return false;
    }
  }
  while (p < pattern.size() && pattern[p] == '*') ++p;
  return p == pattern.size();
}

Options ParseArgs(int argc, char** argv) {
  Options options;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    auto requireValue = [&](const std::string& name) -> std::string {
      if (i + 1 >= argc) throw std::runtime_error("Missing value for " + name);
      return argv[++i];
    };
    if (arg == "--input") {
      options.inputDir = requireValue(arg);
    } else if (arg == "--pattern") {
      options.pattern = requireValue(arg);
    } else if (arg == "--output") {
      options.output = requireValue(arg);
    } else if (arg == "--help" || arg == "-h") {
      std::cout
          << "Usage:\n"
          << "  mergeHistograms --input output/run1 --pattern "
             "hist_edep_raw_t*.csv --output merged.csv\n"
          << "  mergeHistograms --output merged.csv file1.csv file2.csv\n";
      std::exit(0);
    } else {
      options.files.emplace_back(arg);
    }
  }
  if (options.output.empty()) {
    throw std::runtime_error("--output is required");
  }
  return options;
}

std::vector<fs::path> ResolveInputFiles(const Options& options) {
  std::vector<fs::path> files = options.files;
  if (!options.inputDir.empty()) {
    if (options.pattern.empty()) {
      throw std::runtime_error("--pattern is required when --input is used");
    }
    if (!fs::is_directory(options.inputDir)) {
      throw std::runtime_error("Input directory does not exist: " +
                               options.inputDir.string());
    }
    for (const auto& entry : fs::directory_iterator(options.inputDir)) {
      if (!entry.is_regular_file()) continue;
      const auto name = entry.path().filename().string();
      if (WildcardMatch(options.pattern, name)) {
        files.push_back(entry.path());
      }
    }
  }
  std::sort(files.begin(), files.end());
  if (files.empty()) {
    throw std::runtime_error("No input histogram files were found");
  }
  return files;
}

std::vector<Bin> ReadHistogram(const fs::path& file, bool& explicitMevUnits) {
  std::ifstream input(file);
  if (!input)
    throw std::runtime_error("Cannot open input file: " + file.string());

  std::vector<Bin> bins;
  std::string line;
  int lineNumber = 0;
  int lowColumn = -1;
  int highColumn = -1;
  int countColumn = -1;
  std::size_t columnCount = 0;
  while (std::getline(input, line)) {
    ++lineNumber;
    if (Trim(line).empty()) continue;
    const auto fields = SplitCsvLine(line);
    if (columnCount == 0) {
      if (fields == std::vector<std::string>{"bin", "low_edge_MeV", "high_edge_MeV", "center_MeV", "count"}) {
        lowColumn = 1;
        highColumn = 2;
        countColumn = 4;
        explicitMevUnits = true;
      } else if (fields == std::vector<std::string>{"bin", "low_edge", "high_edge", "center", "count"}) {
        lowColumn = 1;
        highColumn = 2;
        countColumn = 4;
      } else if (fields == std::vector<std::string>{"bin_low", "bin_high", "count"}) {
        lowColumn = 0;
        highColumn = 1;
        countColumn = 2;
      } else {
        throw std::runtime_error(file.string() + ":" + std::to_string(lineNumber) +
                                 ": unsupported histogram CSV header");
      }
      columnCount = fields.size();
      continue;
    }
    if (fields.size() != columnCount) {
      throw std::runtime_error(file.string() + ":" + std::to_string(lineNumber) +
                               ": histogram CSV column count mismatch");
    }
    Bin bin;
    bin.low = ToDouble(fields[lowColumn], file, lineNumber);
    bin.high = ToDouble(fields[highColumn], file, lineNumber);
    if (!(bin.high > bin.low)) {
      throw std::runtime_error(file.string() + ":" + std::to_string(lineNumber) +
                               ": histogram bin requires high > low");
    }
    bin.values.push_back(ToDouble(fields[countColumn], file, lineNumber));
    bins.push_back(bin);
  }
  if (bins.empty()) {
    throw std::runtime_error("No histogram bins found in file: " +
                             file.string());
  }
  return bins;
}

void MergeAndWrite(const std::vector<fs::path>& files, const fs::path& output) {
  std::vector<Bin> merged;
  bool allInputsExplicitMev = true;
  for (std::size_t fileIndex = 0; fileIndex < files.size(); ++fileIndex) {
    bool explicitMevUnits = false;
    auto bins = ReadHistogram(files[fileIndex], explicitMevUnits);
    allInputsExplicitMev = allInputsExplicitMev && explicitMevUnits;
    if (fileIndex == 0) {
      merged = std::move(bins);
      continue;
    }
    if (bins.size() != merged.size()) {
      throw std::runtime_error("Bin count mismatch in file: " +
                               files[fileIndex].string());
    }
    for (std::size_t i = 0; i < bins.size(); ++i) {
      const auto closeEdge = [](double a, double b) {
        return std::abs(a - b) <= 1e-12 + 1e-10 * std::max(std::abs(a), std::abs(b));
      };
      if (!closeEdge(bins[i].low, merged[i].low) ||
          !closeEdge(bins[i].high, merged[i].high)) {
        throw std::runtime_error(
            "Bin edge mismatch in file: " + files[fileIndex].string() +
            ", bin index " + std::to_string(i));
      }
      merged[i].values.push_back(bins[i].values.front());
    }
  }

  if (!output.parent_path().empty()) {
    fs::create_directories(output.parent_path());
  }
  if (fs::exists(output)) {
    throw std::runtime_error("Output file already exists: " + output.string());
  }

  // Reserve a private sibling directory, then expose the completed file with
  // a hard link. Publishing cannot replace an existing result on either OS.
  fs::path temporaryDir;
  const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
  for (unsigned attempt = 0; attempt < 1000; ++attempt) {
    fs::path candidate = output;
    candidate += ".tmp." + std::to_string(nonce) + "." + std::to_string(attempt);
    std::error_code error;
    if (fs::create_directory(candidate, error)) {
      temporaryDir = std::move(candidate);
      break;
    }
    if (error && error != std::errc::file_exists) {
      throw fs::filesystem_error("Cannot reserve temporary output directory", candidate, error);
    }
  }
  if (temporaryDir.empty()) {
    throw std::runtime_error("Cannot reserve temporary output directory for: " + output.string());
  }
  const fs::path temporaryFile = temporaryDir / output.filename();
  try {
    std::ofstream out(temporaryFile);
    if (!out)
      throw std::runtime_error("Cannot open temporary output file: " + temporaryFile.string());
    out << (allInputsExplicitMev
        ? "bin_low_MeV,bin_high_MeV,sum,mean,stddev,n_files\n"
        : "bin_low,bin_high,sum,mean,stddev,n_files\n");
    for (const auto& bin : merged) {
      double sum = 0.0;
      for (double value : bin.values) sum += value;
      const double mean = sum / static_cast<double>(bin.values.size());
      double variance = 0.0;
      for (double value : bin.values) {
        const double diff = value - mean;
        variance += diff * diff;
      }
      variance /= static_cast<double>(bin.values.size());
      out << bin.low << ',' << bin.high << ',' << sum << ',' << mean << ','
          << std::sqrt(variance) << ',' << bin.values.size() << '\n';
    }
    out.flush();
    if (!out) throw std::runtime_error("Failed to write histogram output: " + temporaryFile.string());
    out.close();
    if (!out) throw std::runtime_error("Failed to close histogram output: " + temporaryFile.string());
    fs::create_hard_link(temporaryFile, output);
  } catch (...) {
    std::error_code ignored;
    fs::remove(temporaryFile, ignored);
    fs::remove(temporaryDir, ignored);
    throw;
  }
  std::error_code ignored;
  fs::remove(temporaryFile, ignored);
  fs::remove(temporaryDir, ignored);
}

int main(int argc, char** argv) {
  if (argc == 2 && std::string(argv[1]) == "--source-fingerprint") {
#ifdef G4USIM_MERGE_SOURCE_SHA256
    std::cout << G4USIM_MERGE_SOURCE_SHA256 << '\n';
    return 0;
#else
    std::cerr << "mergeHistograms source fingerprint is unavailable\n";
    return 1;
#endif
  }
  try {
    const Options options = ParseArgs(argc, argv);
    const auto files = ResolveInputFiles(options);
    MergeAndWrite(files, options.output);
    std::cout << "Merged " << files.size() << " histogram files into "
              << options.output.string() << "\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "mergeHistograms error: " << error.what() << "\n";
    return 1;
  }
}
