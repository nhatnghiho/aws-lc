# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

docker build --no-cache -t aws-lc/windows_base:2022 .\windows_base
docker build --no-cache -t vs2015 .\vs2015
docker build --no-cache -t vs2017 .\vs2017
