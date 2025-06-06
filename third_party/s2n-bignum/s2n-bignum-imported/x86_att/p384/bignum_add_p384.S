// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0 OR ISC OR MIT-0

// ----------------------------------------------------------------------------
// Add modulo p_384, z := (x + y) mod p_384, assuming x and y reduced
// Inputs x[6], y[6]; output z[6]
//
//    extern void bignum_add_p384
//     (uint64_t z[static 6], uint64_t x[static 6], uint64_t y[static 6]);
//
// Standard x86-64 ABI: RDI = z, RSI = x, RDX = y
// Microsoft x64 ABI:   RCX = z, RDX = x, R8 = y
// ----------------------------------------------------------------------------

#include "_internal_s2n_bignum.h"


        S2N_BN_SYM_VISIBILITY_DIRECTIVE(bignum_add_p384)
        S2N_BN_SYM_PRIVACY_DIRECTIVE(bignum_add_p384)
        .text

#define z %rdi
#define x %rsi
#define y %rdx

#define d0 %rax
#define d1 %rcx
#define d2 %r8
#define d3 %r9
#define d4 %r10
#define d5 %r11

// Re-use the input pointers as temporaries once we're done

#define a %rsi
#define c %rdx

#define ashort %esi
#define cshort %edx



S2N_BN_SYMBOL(bignum_add_p384):
        _CET_ENDBR

#if WINDOWS_ABI
        pushq   %rdi
        pushq   %rsi
        movq    %rcx, %rdi
        movq    %rdx, %rsi
        movq    %r8, %rdx
#endif

// Add the inputs as 2^384 * c + [d5;d4;d3;d2;d1;d0] = x + y
// This could be combined with the next block using ADCX and ADOX.

        movq    (x), d0
        addq    (y), d0
        movq    8(x), d1
        adcq    8(y), d1
        movq    16(x), d2
        adcq    16(y), d2
        movq    24(x), d3
        adcq    24(y), d3
        movq    32(x), d4
        adcq    32(y), d4
        movq    40(x), d5
        adcq    40(y), d5
        movl    $0, cshort
        adcq    c, c

// Now subtract p_384 from 2^384 * c + [d5;d4;d3;d2;d1;d0] to get x + y - p_384
// This is actually done by *adding* the 7-word negation r_384 = 2^448 - p_384
// where r_384 = [-1; 0; 0; 0; 1; 0x00000000ffffffff; 0xffffffff00000001]

        movq    $0xffffffff00000001, a
        addq    a, d0
        movl    $0x00000000ffffffff, ashort
        adcq    a, d1
        adcq    $1, d2
        adcq    $0, d3
        adcq    $0, d4
        adcq    $0, d5
        adcq    $-1, c

// Since by hypothesis x < p_384 we know x + y - p_384 < 2^384, so the top
// carry c actually gives us a bitmask for x + y - p_384 < 0, which we
// now use to make r' = mask * (2^384 - p_384) for a compensating subtraction.
// We don't quite have enough ABI-modifiable registers to create all three
// nonzero digits of r while maintaining d0..d5, but make the first two now.

        andq    a, c // c = masked 0x00000000ffffffff
        xorq    a, a
        subq    c, a // a = masked 0xffffffff00000001

// Do the first two digits of addition and writeback

        subq    a, d0
        movq    d0, (z)
        sbbq    c, d1
        movq    d1, 8(z)

// Preserve the carry chain while creating the extra masked digit since
// the logical operation will clear CF

        sbbq    d0, d0
        andq    a, c // c = masked 0x0000000000000001
        negq    d0

// Do the rest of the addition and writeback

        sbbq    c, d2
        movq    d2, 16(z)
        sbbq    $0, d3
        movq    d3, 24(z)
        sbbq    $0, d4
        movq    d4, 32(z)
        sbbq    $0, d5
        movq    d5, 40(z)

#if WINDOWS_ABI
        popq   %rsi
        popq   %rdi
#endif
        ret

#if defined(__linux__) && defined(__ELF__)
.section .note.GNU-stack,"",%progbits
#endif
