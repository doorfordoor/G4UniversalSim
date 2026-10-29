#include "Config/InputProvenance.hh"
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iterator>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <vector>
namespace input_provenance {
namespace {
std::uint32_t R(std::uint32_t x, unsigned n) { return (x >> n) | (x << (32-n)); }
constexpr std::uint32_t K[] = {
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
}
std::string Sha256(std::string_view bytes) {
 if (bytes.size() > std::numeric_limits<std::uint64_t>::max()/8) throw std::length_error("SHA256 input too long");
 const auto bits=static_cast<std::uint64_t>(bytes.size())*8;
 std::vector<unsigned char> data(bytes.begin(),bytes.end()); data.push_back(0x80);
 while(data.size()%64!=56) data.push_back(0);
 for(int i=7;i>=0;--i) data.push_back(static_cast<unsigned char>(bits>>(i*8)));
 std::array<std::uint32_t,8> h{{0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19}};
 for(std::size_t block=0;block<data.size();block+=64) {
  std::uint32_t w[64]{};
  for(unsigned i=0;i<16;++i) for(unsigned j=0;j<4;++j) w[i]=(w[i]<<8)|data[block+i*4+j];
  for(unsigned i=16;i<64;++i) {auto a=w[i-15],b=w[i-2];w[i]=w[i-16]+(R(a,7)^R(a,18)^(a>>3))+w[i-7]+(R(b,17)^R(b,19)^(b>>10));}
  auto a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],v=h[7];
  for(unsigned i=0;i<64;++i) {auto t1=v+(R(e,6)^R(e,11)^R(e,25))+((e&f)^((~e)&g))+K[i]+w[i];auto t2=(R(a,2)^R(a,13)^R(a,22))+((a&b)^(a&c)^(b&c));v=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;}
  h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=v;
 }
 std::ostringstream out;out<<std::hex<<std::setfill('0');for(auto x:h) out<<std::setw(8)<<x;return out.str();
}
InputFile ReadFile(const std::string& path) {
 if(!std::filesystem::is_regular_file(std::filesystem::u8path(path))) throw std::runtime_error("Input file does not exist or is not regular: '"+path+"'");
 std::ifstream input(std::filesystem::u8path(path),std::ios::binary);
 if(!input) throw std::runtime_error("Failed to open input file: '"+path+"'");
 std::string bytes((std::istreambuf_iterator<char>(input)),std::istreambuf_iterator<char>());
 if(input.bad()) throw std::runtime_error("Failed while reading input file: '"+path+"'");
 auto digest=Sha256(bytes);return {path,std::move(bytes),std::move(digest)};
}
}
