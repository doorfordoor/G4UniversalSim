#pragma once

#include "Geometry/GdmlComponent.hh"
#include "G4RotationMatrix.hh"
#include "G4ThreeVector.hh"

#include <array>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>

namespace gdml_affine {
inline double length(const G4ThreeVector& v) {
    return std::hypot(v.x(),v.y(),v.z());
}
inline G4ThreeVector scale(const std::array<double,3>& d,const G4ThreeVector& v) {
    return {d[0]*v.x(),d[1]*v.y(),d[2]*v.z()};
}
struct Box {
    G4RotationMatrix axes;
    G4ThreeVector half;
    double alpha=0,theta=0,phi=0;
    bool rectangular=false;
};

// Columns of D R diag(h) are the desired half edges in the component-root frame.
inline Box decompose(const std::array<double,3>& d,const G4RotationMatrix& r,
                     const G4ThreeVector& h,const G4ThreeVector& center,
                     double tolerance,const std::string& path) {
    const auto check=[&](bool accepted,const char* reason) {
        if(!accepted)throw GdmlIO::ComponentScaleError("GDML component scales at "+path+": "+reason);
    };
    const G4ThreeVector edge[]{scale(d,r.colX()*h.x()),scale(d,r.colY()*h.y()),scale(d,r.colZ()*h.z())};
    G4ThreeVector direction[3];
    const double centerLength=length(center);
    check(std::isfinite(centerLength),"unrepresentable center");
    const double minThickness=std::max(2*tolerance,16*std::numeric_limits<double>::epsilon()*centerLength);
    for(int i=0;i<3;++i) {
        const double n=length(edge[i]);
        check(std::isfinite(n) && n>minThickness && std::isfinite(edge[i].mag2()),"unrepresentable edge length");
        direction[i]=edge[i]/n;
    }
    for(int i=0;i<3;++i) {
        const auto n=direction[(i+1)%3].cross(direction[(i+2)%3]);
        const double mag=length(n);
        check(std::isfinite(mag) && mag>0 && edge[i].dot(n/mag)>minThickness,
              "unresolved plane spacing or handedness");
        const auto face=edge[(i+1)%3].cross(edge[(i+2)%3]);
        check(std::isfinite(face.mag2()) && face.mag2()>0,"unrepresentable face area");
    }
    const auto x=direction[0];
    const auto z=x.cross(direction[1]).unit();
    const auto y=z.cross(x);
    Box result;
    result.axes=G4RotationMatrix(x,y,z);
    result.half={length(edge[0]),edge[1].dot(y),edge[2].dot(z)};
    const double b=edge[1].dot(x), c=edge[2].dot(x), e=edge[2].dot(y);
    result.alpha=std::atan2(b,result.half.y());
    result.theta=std::atan2(std::hypot(c,e),result.half.z());
    result.phi=std::atan2(e,c);
    result.rectangular=(d[0]==d[1] && d[1]==d[2]) || (b==0 && c==0 && e==0);
    const double volume=8*result.half.x()*result.half.y()*result.half.z();
    check(std::isfinite(volume) && volume>0,"unrepresentable solid volume");
    const double shearY=result.rectangular?0:std::tan(result.alpha)*result.half.y();
    const double tilt=result.rectangular?0:std::tan(result.theta)*result.half.z();
    const G4ThreeVector local[]{ {result.half.x(),0,0},{shearY,result.half.y(),0},
        {tilt*std::cos(result.phi),tilt*std::sin(result.phi),result.half.z()} };
    for(int i=0;i<3;++i) {
        const double err=length(result.axes*local[i]-edge[i]);
        check(std::isfinite(err) && err<=1e-12*length(edge[i]) && err<=tolerance,
              "native box/para parameter reconstruction exceeds precision");
    }
    for(int i:{-1,1})for(int j:{-1,1})for(int k:{-1,1}) {
        const auto corner=center+i*edge[0]+j*edge[1]+k*edge[2];
        check(std::isfinite(length(corner)),"unrepresentable transformed corner");
    }
    return result;
}
}
