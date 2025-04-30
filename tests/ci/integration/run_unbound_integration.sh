#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

set -exu

source tests/ci/common_posix_setup.sh

# Set up environment.

# SYS_ROOT
#  |
#  - SRC_ROOT(aws-lc)
#  |
#  - SCRATCH_FOLDER
#    |
#    - unbound
#    - UNBOUND_BUILD_FOLDER
#    - UNBOUND_INSTALL_FOLDER
#    - AWS_LC_BUILD_FOLDER
#    - AWS_LC_INSTALL_FOLDER

# Assumes script is executed from the root of aws-lc directory
SCRATCH_FOLDER=${SRC_ROOT}/"UNBOUND_BUILD_ROOT"
UNBOUND_SRC_FOLDER="${SCRATCH_FOLDER}/unbound"
UNBOUND_BUILD_PREFIX="${UNBOUND_SRC_FOLDER}/build/install"
UNBOUND_BUILD_EPREFIX="${UNBOUND_SRC_FOLDER}/build/exec-install"
AWS_LC_BUILD_FOLDER="${SCRATCH_FOLDER}/aws-lc-build"
AWS_LC_INSTALL_FOLDER="${SCRATCH_FOLDER}/aws-lc-install"

mkdir -p "${SCRATCH_FOLDER}"
rm -rf "${SCRATCH_FOLDER:?}"/*

# ONLY HERE TO AVOID AN EXTRA MCM. SHOULD BE REMOVED ONCE PIPELINE IS LIVE
function install_expat() {
  export IOS_PREFIX="/usr"
  ./contrib/ios/install_expat.sh
}

function unbound_build() {
  pushd "${UNBOUND_SRC_FOLDER}"
  install_expat
  CFLAGS='-Wno-deprecated-declarations' ./configure --disable-ed448 \
              --prefix="${UNBOUND_BUILD_PREFIX}" \
              --exec-prefix="${UNBOUND_BUILD_EPREFIX}" \
              --with-ssl="${AWS_LC_INSTALL_FOLDER}" \
              --with-libexpat="$IOS_PREFIX"
  make -j "${NUM_CPU_THREADS}"
  make -j install

  local unbound_executable="${UNBOUND_BUILD_EPREFIX}/lib/libunbound.so"
      ldd ${unbound_executable} \
        | grep "${AWS_LC_INSTALL_FOLDER}/lib/libcrypto.so" || exit 1
}

function unbound_parse_test_results() {
  PERMITTED_FAILS="01-doc
  stat_values"

  results=$(echo "$1" | sed -n "/Minitdir Report/,\$p")
  echo "$results"

  # Initialize arrays for actual results
  local passed=()
  local failed=()
  local skipped=()

  # Read the output and categorize
  while IFS= read -r line; do
      if [[ $line =~ ^"** PASSED ** : "(.*)$ ]]; then
          passed+=("${BASH_REMATCH[1]}")
      elif [[ $line =~ ^"!! FAILED !! : "(.*)$ ]]; then
          failed+=("${BASH_REMATCH[1]}")
      elif [[ $line =~ ^".. SKIPPED.. : "(.*)$ ]]; then
          skipped+=("${BASH_REMATCH[1]}")
      fi
  done <<< "$results"

  # Use grep to find unexpected failures
  mapfile -t unexpected_fails < <(printf '%s\n' "${failed[@]}" | grep -vFf <(echo "$PERMITTED_FAILS") || true)

  # Print results
  echo -e "\n=== Test Results Summary ==="
  echo "Passed tests (${#passed[@]}):"
  printf '%s\n' "${passed[@]}"

  echo -e "\nSkipped tests (${#skipped[@]}):"
  printf '%s\n' "${skipped[@]}"

  echo -e "\nFailed tests (${#failed[@]}):"
  printf '%s\n' "${failed[@]}"

  echo -e "\nUnexpected failures:"
  if [ ${#unexpected_fails[@]} -eq 0 ]; then
      echo "None"
  else
      printf '%s\n' "${unexpected_fails[@]}"
  fi

  # Exit with error if there are unexpected failures or skips
  if [ ${#unexpected_fails[@]} -gt 0 ]; then
      echo -e "\nTest failed due to unexpected failures"
      exit 1
  fi

  echo -e "\nAll tests passed within expected parameters"
}

function unbound_run_tests() {
  export PATH="${UNBOUND_BUILD_EPREFIX}/sbin/:$PATH"
  local results=$(make longtest)
  unbound_parse_test_results output
  popd
}

pushd "${SCRATCH_FOLDER}"

# Get latest unbound version.
git clone https://github.com/NLnetLabs/unbound.git "${UNBOUND_SRC_FOLDER}"
mkdir -p "${AWS_LC_BUILD_FOLDER}" "${AWS_LC_INSTALL_FOLDER}" "${UNBOUND_BUILD_PREFIX}" "${UNBOUND_BUILD_EPREFIX}"
ls

aws_lc_build "$SRC_ROOT" "$AWS_LC_BUILD_FOLDER" "$AWS_LC_INSTALL_FOLDER" -DBUILD_TESTING=OFF -DBUILD_TOOL=OFF -DCMAKE_BUILD_TYPE=RelWithDebInfo -DBUILD_SHARED_LIBS=1
export LD_LIBRARY_PATH="${AWS_LC_INSTALL_FOLDER}/lib/:${AWS_LC_INSTALL_FOLDER}/lib64/:${LD_LIBRARY_PATH:-}"
ln -s ${AWS_LC_INSTALL_FOLDER}/lib64 ${AWS_LC_INSTALL_FOLDER}/lib

unbound_build
unbound_run_tests

popd

