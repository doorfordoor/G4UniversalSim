#pragma once
#include "G4AtRestObserverV1.h"
#include <cstddef>
#include <stdexcept>
#include <vector>

namespace activation_observation {
static_assert(sizeof(G4AtRestObserverV1Row) == 120);
static_assert(offsetof(G4AtRestObserverV1Row, run_id) == 88);
static_assert(offsetof(G4AtRestObserverV1Row, branch) == 116);

// Construct only for an explicitly enabled worker. Lifetime is confined to that worker.
class NativeClockScope final {
public:
    explicit NativeClockScope(std::size_t capacity) : rows_(capacity) {
        if (capacity == 0) throw std::invalid_argument("empty native clock buffer");
    }
    NativeClockScope(const NativeClockScope&) = delete;
    NativeClockScope& operator=(const NativeClockScope&) = delete;
    ~NativeClockScope() { Discard(); }

    void Begin(int run, int event, int worker) {
        if (token_) {
            Discard();
            throw std::logic_error("unclosed native clock event");
        }
        if (run < 0 || event < 0) throw std::invalid_argument("invalid native event identity");
        const uint64_t token = (uint64_t(run) << 32) | (uint64_t(event) + 1);
        const auto rc = G4AtRestObserverV1Begin(sizeof(Row), token, run, event, worker,
                                               rows_.data(), rows_.size());
        if (rc != G4_AT_REST_OBSERVER_V1_OK) throw std::runtime_error("native clock begin failed");
        token_ = token;
        run_ = run;
        event_ = event;
        worker_ = worker;
    }

    // Consumer receives the entire validated event and must stage publication.
    template<class Consumer> void Close(int run, int event, int worker, Consumer consume) {
        const uint64_t original = token_;
        uint64_t count = 0;
        const auto rc = original ? G4AtRestObserverV1End(original, &count)
                                 : G4_AT_REST_OBSERVER_V1_NOT_BOUND;
        token_ = 0;
        if (rc != G4_AT_REST_OBSERVER_V1_OK || run != run_ || event != event_ ||
            worker != worker_ || count > rows_.size())
            throw std::runtime_error("native clock close or identity failed");
        for (uint64_t i = 0; i < count; ++i) {
            const auto& row = rows_[i];
            if (row.token != original || row.ordinal != i || row.run_id != run ||
                row.event_id != event || row.worker_id != worker || row.track_id <= 0 ||
                row.step_number <= 0 || row.parent_id < 0 ||
                (row.branch != G4_AT_REST_OBSERVER_V1_CONTINUED &&
                 row.branch != G4_AT_REST_OBSERVER_V1_CUTOFF))
                throw std::runtime_error("invalid native clock row");
        }
        consume(rows_.data(), count);
    }
    void Discard() noexcept {
        if (token_) {
            uint64_t ignored = 0;
            G4AtRestObserverV1End(token_, &ignored);
            token_ = 0;
        }
    }
private:
    using Row = G4AtRestObserverV1Row;
    std::vector<Row> rows_;
    uint64_t token_ = 0;
    int run_ = -1, event_ = -1, worker_ = -1;
};
}
