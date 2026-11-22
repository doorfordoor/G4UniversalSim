#pragma once
#include "G4VTouchable.hh"
namespace engineering_event {
inline bool SameEmptyDownstreamTouchable(const G4VTouchable* post, const G4VTouchable* next) {
    return post && post == next && !post->GetVolume();
}
}
