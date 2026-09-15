// Test entry point. Walks the registered test list, runs each one, prints a
// per-case status line, and returns non-zero if any check failed. Kept in
// its own TU so the header stays include-guard-friendly.

#include "test_framework.h"

#include <cstdio>

int main() {
    int totalFails = 0;
    int totalCases = 0;
    for (const auto& c : nasty::test::registry()) {
        int fails = 0;
        c.fn(fails);
        ++totalCases;
        if (fails == 0) {
            std::printf("  ok   %s\n", c.name);
        } else {
            totalFails += fails;
            std::printf("  FAIL %s  (%d check%s)\n", c.name, fails, fails == 1 ? "" : "s");
        }
    }
    std::printf("\n%d test%s, %d failure%s\n",
                totalCases, totalCases == 1 ? "" : "s",
                totalFails, totalFails == 1 ? "" : "s");
    return totalFails == 0 ? 0 : 1;
}
