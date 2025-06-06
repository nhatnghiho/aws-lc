// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0 OR ISC OR MIT-0

// ----------------------------------------------------------------------------
// Add modulo p_25519, z := (x + y) mod p_25519, assuming x and y reduced
// Inputs x[4], y[4]; output z[4]
//
//    extern void bignum_add_p25519
//     (uint64_t z[static 4], uint64_t x[static 4], uint64_t y[static 4]);
//
// Standard x86-64 ABI: RDI = z, RSI = x, RDX = y
// Microsoft x64 ABI:   RCX = z, RDX = x, R8 = y
// ----------------------------------------------------------------------------

#include "_internal_s2n_bignum.h"


        S2N_BN_SYM_VISIBILITY_DIRECTIVE(bignum_add_p25519)
        S2N_BN_SYM_PRIVACY_DIRECTIVE(bignum_add_p25519)
        .text

#define z %rdi
#define x %rsi
#define y %rdx

#define d0 %r8
#define d1 %r9
#define d2 %r10
#define d3 %r11

// These also re-use inputs x and y when safe to do so

#define c0 %rax
#define c1 %rcx
#define c2 %rsi
#define c3 %rdx
#define c0short %eax
#define c1short %ecx
#define c2short %esi
#define c3short %edx

S2N_BN_SYMBOL(bignum_add_p25519):
        _CET_ENDBR

#if WINDOWS_ABI
        pushq   %rdi
        pushq   %rsi
        movq    %rcx, %rdi
        movq    %rdx, %rsi
        movq    %r8, %rdx
#endif

// Add as [d3; d2; d1; d0] = x + y; since we assume x, y < 2^255 - 19
// this sum fits in 256 bits.

        movq    (x), d0
        addq    (y), d0
        movq    8(x), d1
        adcq    8(y), d1
        movq    16(x), d2
        adcq    16(y), d2
        movq    24(x), d3
        adcq    24(y), d3

// Now x + y >= 2^255 - 19 <=> x + y + 19 >= 2^255.
// Form [c3; c2; c1; c0] = (x + y) + 19

        movl    $19, c0short
        xorl    c1short, c1short
        xorl    c2short, c2short
        xorl    c3short, c3short

        addq    d0, c0
        adcq    d1, c1
        adcq    d2, c2
        adcq    d3, c3

// Test the top bit to see if this is >= 2^255, and clear it as a masking
// so that in that case the result is exactly (x + y) - (2^255 - 19).
// Then select the output according to that top bit as that or just x + y.

        btr     $63, c3
        cmovcq  c0, d0
        cmovcq  c1, d1
        cmovcq  c2, d2
        cmovcq  c3, d3

// Store the result

        movq    d0, (z)
        movq    d1, 8(z)
        movq    d2, 16(z)
        movq    d3, 24(z)

#if WINDOWS_ABI
        popq   %rsi
        popq   %rdi
#endif
        ret

#if defined(__linux__) && defined(__ELF__)
.section .note.GNU-stack,"",%progbits
#endif
