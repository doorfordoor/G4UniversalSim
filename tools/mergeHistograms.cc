#include <algorithm>
#include <cmath>
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
  if (end == trimmed.c_str() || !Trim(std::string(end)).empty()) {
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

std::vector<Bin> ReadHistogram(const fs::path& file) {
  std::ifstream input(file);
  if (!input)
    throw std::runtime_error("Cannot open input file: " + file.string());

  std::vector<Bin> bins;
  std::string line;
  int lineNumber = 0;
  while (std::getline(input, line)) {
    ++lineNumber;
    if (Trim(line).empty()) continue;
    const auto fields = SplitCsvLine(line);
    if (fields.size() < 3) {
      throw std::runtime_error(file.string() + ":" +
                               std::to_string(lineNumber) +
                               ": expected at least 3 CSV fields");
    }
    if (!IsNumber(fields[0])) {
      continue;  // header
    }
    Bin bin;
    bin.low = ToDouble(fields[0], file, lineNumber);
    bin.high = ToDouble(fields[1], file, lineNumber);
    bin.values.push_back(ToDouble(fields[2], file, lineNumber));
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
  for (std::size_t fileIndex = 0; fileIndex < files.size(); ++fileIndex) {
    auto bins = ReadHistogram(files[fileIndex]);
    if (fileIndex == 0) {
      merged = std::move(bins);
      continue;
    }
    if (bins.size() != merged.size()) {
      throw std::runtime_error("Bin count mismatch in file: " +
                               files[fileIndex].string());
    }
    for (std::size_t i = 0; i < bins.size(); ++i) {
      if (bins[i].low != merged[i].low || bins[i].high != merged[i].high) {
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
  std::ofstream out(output);
  if (!out)
    throw std::runtime_error("Cannot open output file: " + output.string());
  out << "bin_low,bin_high,sum,mean,stddev,n_files\n";
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
}

int main(int argc, char** argv) {
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
