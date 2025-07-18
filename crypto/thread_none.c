/* Copyright (c) 2015, Google Inc.
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
 * SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION
 * OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
 * CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE. */

#include "internal.h"

#if !defined(OPENSSL_THREADS)

void CRYPTO_MUTEX_init(CRYPTO_MUTEX *lock) {}

void CRYPTO_MUTEX_lock_read(CRYPTO_MUTEX *lock) {}

void CRYPTO_MUTEX_lock_write(CRYPTO_MUTEX *lock) {}

void CRYPTO_MUTEX_unlock_read(CRYPTO_MUTEX *lock) {}

void CRYPTO_MUTEX_unlock_write(CRYPTO_MUTEX *lock) {}

void CRYPTO_MUTEX_cleanup(CRYPTO_MUTEX *lock) {}

void CRYPTO_STATIC_MUTEX_lock_read(struct CRYPTO_STATIC_MUTEX *lock) {}

void CRYPTO_STATIC_MUTEX_lock_write(struct CRYPTO_STATIC_MUTEX *lock) {}

void CRYPTO_STATIC_MUTEX_unlock_read(struct CRYPTO_STATIC_MUTEX *lock) {}

void CRYPTO_STATIC_MUTEX_unlock_write(struct CRYPTO_STATIC_MUTEX *lock) {}

#if !defined(NDEBUG)
int CRYPTO_STATIC_MUTEX_is_write_locked(struct CRYPTO_STATIC_MUTEX *lock) {
  return 1;
}
#endif

void CRYPTO_once(CRYPTO_once_t *once, void (*init)(void)) {
  if (*once) {
    return;
  }
  *once = 1;
  init();
}

static void *g_thread_locals[NUM_OPENSSL_THREAD_LOCALS];

void *CRYPTO_get_thread_local(thread_local_data_t index) {
  return g_thread_locals[index];
}

int CRYPTO_set_thread_local(thread_local_data_t index, void *value,
                            thread_local_destructor_t destructor) {
  g_thread_locals[index] = value;
  return 1;
}

#endif  // !OPENSSL_THREADS
