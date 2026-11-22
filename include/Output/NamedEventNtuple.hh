#pragma once

#include <map>
#include <string>
#include <vector>

class CsvWriter;

struct NamedEventNtuple {
    std::string name;
    std::vector<std::string> columns;
    std::vector<std::string> Header() const;
    static bool IsEnergyColumn(const std::string& column);
    static bool MatchesHeader(const std::string& header);
};

struct EventNtupleShard {
    std::string path;
    std::string sha256;
    int rows;
};

// Input streams retain one finite, typed row per worker. Output preserves
// the originating worker and the exact decimal representation of each value.
void MergeEventNtuple(const NamedEventNtuple& definition, const std::map<int, EventNtupleShard>& shards,
                      int runId, int completed, CsvWriter& destination);
