// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: Apache-2.0 OR ISC OR MIT-0

// ----------------------------------------------------------------------------
// Test bignums for equality, x = y
// Inputs x[m], y[n]; output function return
//
//    extern uint64_t bignum_eq
//     (uint64_t m, uint64_t *x, uint64_t n, uint64_t *y);
//
// Standard x86-64 ABI: RDI = m, RSI = x, RDX = n, RCX = y, returns RAX
// Microsoft x64 ABI:   RCX = m, RDX = x, R8 = n, R9 = y, returns RAX
// ----------------------------------------------------------------------------

#include "_internal_s2n_bignum.h"


        S2N_BN_SYM_VISIBILITY_DIRECTIVE(bignum_eq)
        S2N_BN_SYM_PRIVACY_DIRECTIVE(bignum_eq)
        .text

#define m %rdi
#define x %rsi
#define n %rdx
#define y %rcx
#define c %rax
// We can re-use n for this, not needed when d appears
#define d %rdx

S2N_BN_SYMBOL(bignum_eq):
        _CET_ENDBR

#if WINDOWS_ABI
        pushq   %rdi
        pushq   %rsi
        movq    %rcx, %rdi
        movq    %rdx, %rsi
        movq    %r8, %rdx
        movq    %r9, %rcx
#endif

// Initialize the accumulated OR of differences to zero

        xorq    c, c

// If m >= n jump into the m > n loop at the final equality test
// This will drop through for m = n

        cmpq    n, m
        jnc     bignum_eq_mtest

// Toploop for the case n > m

bignum_eq_nloop:
        decq    n
        orq     (y,n,8), c
        cmpq    n, m
        jnz     bignum_eq_nloop
        jmp     bignum_eq_mmain

// Toploop for the case m > n (or n = m which enters at "mtest")

bignum_eq_mloop:
        decq    m
        orq     (x,m,8), c
        cmpq    n, m
bignum_eq_mtest:
        jnz     bignum_eq_mloop

// Combined main loop for the min(m,n) lower words

bignum_eq_mmain:
        testq   m, m
        jz      bignum_eq_end

bignum_eq_loop:
        movq    -8(x,m,8), d
        xorq    -8(y,m,8), d
        orq     d, c
        decq    m
        jnz     bignum_eq_loop

// Set a standard C condition based on whether c is nonzero

bignum_eq_end:
        negq    c
        sbbq    c, c
        incq    c
#if WINDOWS_ABI
        popq   %rsi
        popq   %rdi
#endif
        ret

#if defined(__linux__) && defined(__ELF__)
.section .note.GNU-stack,"",%progbits
#endif
