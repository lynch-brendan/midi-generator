#pragma once

// Tiny header-only unit-test harness. Zero external deps by design — these
// tests exercise the leaf audio primitives (Transport, PatternPlayer) that
// have zero JUCE surface, so the tests should also have zero framework
// surface. The whole harness fits on one page.
//
// Usage:
//   TEST(MyThing_does_the_expected) {
//       CHECK(x == 42);
//       CHECK_EQ(y, 7);
//   }
// Test binary links in test_main.cpp for the entry point.

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace nasty {
namespace test {

struct Case {
    const char* name;
    void (*fn)(int&);
};

inline std::vector<Case>& registry() {
    static std::vector<Case> r;
    return r;
}

struct Registrar {
    Registrar(const char* name, void (*fn)(int&)) { registry().push_back({name, fn}); }
};

} // namespace test
} // namespace nasty

#define TEST(name)                                                             \
    static void name(int& _nasty_fail_count);                                  \
    static ::nasty::test::Registrar _nasty_reg_##name{#name, &name};           \
    static void name(int& _nasty_fail_count)

#define CHECK(cond)                                                            \
    do {                                                                       \
        if (!(cond)) {                                                         \
            ++_nasty_fail_count;                                                \
            std::fprintf(stderr, "  FAIL %s:%d  CHECK(%s)\n",                  \
                         __FILE__, __LINE__, #cond);                           \
        }                                                                      \
    } while (0)

#define CHECK_EQ(a, b)                                                         \
    do {                                                                       \
        auto _a = (a);                                                         \
        auto _b = (b);                                                         \
        if (!(_a == _b)) {                                                     \
            ++_nasty_fail_count;                                                \
            std::fprintf(stderr, "  FAIL %s:%d  CHECK_EQ(%s, %s)  "            \
                         "got %lld vs %lld\n",                                 \
                         __FILE__, __LINE__, #a, #b,                           \
                         (long long)_a, (long long)_b);                       \
        }                                                                      \
    } while (0)

