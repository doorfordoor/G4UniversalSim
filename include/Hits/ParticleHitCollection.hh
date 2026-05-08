#pragma once

#include "G4THitsCollection.hh"

#include "Hits/ParticleHit.hh"
#include "Output/OutputRecord.hh"

#include <vector>

using ParticleHitCollection = G4THitsCollection<ParticleHit>;

std::vector<HitRecord> ConvertToHitRecords(const ParticleHitCollection* collection);
