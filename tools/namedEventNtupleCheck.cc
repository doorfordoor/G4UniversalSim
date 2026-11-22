#include "Output/NamedEventNtuple.hh"
#include "Output/CsvWriter.hh"
#include "Config/InputProvenance.hh"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    try {
        const std::filesystem::path directory(argv[1]);
        std::filesystem::create_directories(directory);
        const NamedEventNtuple definition{"test", {"raw_edep_MeV"}};
        const std::string header = "run_id,event_id,thread_id,raw_edep_MeV\n";
        const auto check = [&](const char* name, const std::string& a, const std::string& b,
                               int nA, int nB, int completed, bool pass, bool changeHash = false) {
            std::map<int, EventNtupleShard> shards;
            for (int worker = 0; worker < 2; ++worker) {
                const auto path = directory / (std::string(name) + std::to_string(worker) + ".csv");
                const auto& bytes = worker == 0 ? a : b;
                std::ofstream file(path, std::ios::binary);
                file << bytes;
                file.close();
                if (!file) throw std::runtime_error("cannot create test shard");
                const auto hash = input_provenance::Sha256(bytes);
                shards[worker] = {path.string(), changeHash && worker == 0 ? std::string(64, '0') : hash,
                                  worker == 0 ? nA : nB};
            }
            CsvWriter output((directory / (std::string(name) + "-out.csv")).string());
            bool accepted = true;
            try {
                MergeEventNtuple(definition, shards, 0, completed, output);
            } catch (const std::runtime_error&) {
                accepted = false;
            }
            output.Close();
            if (accepted != pass) throw std::runtime_error(std::string("unexpected merge decision: ") + name);
        };
        const auto row = header + "0,0,0,4.9406564584124654e-324\n";
        const auto second = header + "0,1,1,1.0000000000000002\n";
        check("ordered", row, second, 1, 1, 2, true);
        check("empty-worker", row, header, 1, 0, 1, true);
        check("empty-run", header, header, 0, 0, 0, true);
        check("duplicate", row, header + "0,0,1,0\n", 1, 1, 2, false);
        check("missing", row, header, 1, 0, 2, false);
        check("late-row", row, second, 1, 0, 1, false);
        check("short", row.substr(0, row.size() - 1), header, 1, 0, 1, false);
        check("trailing", row + "\n", header, 1, 0, 1, false);
        check("oversize", header + std::string(300, '0') + "\n", header, 1, 0, 1, false);
        check("wrong-thread", header + "0,0,1,0\n", header, 1, 0, 1, false);
        check("wrong-run", header + "1,0,0,0\n", header, 1, 0, 1, false);
        check("wrong-header", "run,event,thread,value\n", header, 0, 0, 0, false);
        check("wrong-hash", row, header, 1, 0, 1, false, true);
        check("nan", header + "0,0,0,nan\n", header, 1, 0, 1, false);
        std::cout << "14 streaming merge cases passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
