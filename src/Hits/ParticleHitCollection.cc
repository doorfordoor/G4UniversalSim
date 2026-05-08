#include "Hits/ParticleHitCollection.hh"

std::vector<HitRecord> ConvertToHitRecords(const ParticleHitCollection* collection)
{
    std::vector<HitRecord> records;
    if (!collection) return records;

    const auto count = collection->entries();
    records.reserve(static_cast<std::size_t>(count));
    for (std::size_t i = 0; i < static_cast<std::size_t>(count); ++i) {
        const ParticleHit* hit = (*collection)[static_cast<G4int>(i)];
        if (hit) records.push_back(hit->ToHitRecord());
    }
    return records;
}
