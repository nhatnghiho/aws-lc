#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

set -exuo pipefail

echo \"Environment variables:\"
env

function assume_role() {
  CREDENTIALS=$(aws sts assume-role --role-arn arn:aws:iam::${DEPLOY_ACCOUNT}:role/CrossAccountCodeBuildRole --role-session-name codebuild-session)
  export AWS_ACCESS_KEY_ID=$(echo $CREDENTIALS | jq -r .Credentials.AccessKeyId)
  export AWS_SECRET_ACCESS_KEY=$(echo $CREDENTIALS | jq -r .Credentials.SecretAccessKey)
  export AWS_SESSION_TOKEN=$(echo $CREDENTIALS | jq -r .Credentials.SessionToken)
}

function start_codebuild_project() {
  local project=${1}

  if [[ -z ${project} ]]; then
    echo "No project name provided."
    exit 1
  fi

  # https://awscli.amazonaws.com/v2/documentation/api/latest/reference/codebuild/start-build-batch.html
  build_id=$(aws codebuild start-build-batch --project-name ${project} | jq -r '.buildBatch.id')
  export BUILD_BATCH_ID="${build_id}"

  if [ -z "${BUILD_BATCH_ID}" ]; then
    echo \"Failed to start build\"
    return 1
  fi

  return 0
}

function codebuild_build_status_check() {
  # Every 5 min, this function checks if the linux docker image batch code build finished successfully.
  # Normally, docker img build can take up to 1 hour. Here, we wait up to 30 * 5 min.
  for i in {1..30}; do
    # https://docs.aws.amazon.com/cli/latest/reference/codebuild/batch-get-build-batches.html
    build_batch_status=$(aws codebuild batch-get-build-batches --ids "${BUILD_BATCH_ID}" | jq -r '.buildBatches[0].buildBatchStatus')
    if [[ ${build_batch_status} == 'SUCCEEDED' ]]; then
      echo "Build ${BUILD_BATCH_ID} finished successfully."
      return 0
    elif [[ ${build_batch_status} == 'FAILED' ]]; then
      echo "Build ${BUILD_BATCH_ID} failed."
      exit 1
    else
      echo "${i}: Wait 5 min for build job finish."
      sleep 300
    fi
  done
  echo "Build ${BUILD_BATCH_ID} takes more time than expected."
  return 1
}

function build_codebuild_ci_project() {
  local attempt=0
  local project=${1}

  if [[ -z ${project} ]]; then
      echo "No project name provided."
      exit 1
  fi

  while [[ ${attempt} -le ${MAX_RETRY} ]]; do
    attempt=$((attempt + 1))
    echo "Attempt ${attempt}"
    echo "Running CI tests in ${project}"
    if ! start_codebuild_project "$project"; then
      echo "Failed to start build, retrying ${attempt}/${MAX_RETRY}..."
      continue
    fi

    echo "Waiting for CI tests for complete. This may take anywhere from 15 minutes to 1 hour"
    if ! codebuild_build_status_check; then
        echo "Tests failed, retrying ${attempt}/${MAX_RETRY}..."
        continue
    fi

    echo "All tests completed successfully"
    return
  done

  echo "CI tests failed"
}

function build_linux_docker_images() {
  local attempt=0

  while [[ ${attempt} -le ${MAX_RETRY} ]]; do
    attempt=$((attempt + 1))
    echo "Attempt ${attempt}"
    echo "Activating AWS CodeBuild to build Linux aarch & x86 docker images."
    if ! start_codebuild_project aws-lc-docker-image-build-linux; then
      echo "Failed to start build, retrying ${attempt}/${MAX_RETRY}..."
      continue
    fi

    echo "Waiting for docker images creation. Building the docker images need to take 1 hour."
    # TODO(CryptoAlg-624): These image build may fail due to the Docker Hub pull limits made on 2020-11-01.
    if ! codebuild_build_status_check; then
        echo "Build failed, retrying ${attempt}/${MAX_RETRY}..."
        continue
    fi

    echo "Successfully built Linux docker images"
    return
  done

  echo "Failed to build Linux docker images"
}

function start_windows_img_build() {
  # EC2 takes several minutes to be ready for running command.
  echo "Wait 3 min for EC2 ready for SSM command execution."
  sleep 180

  # Run commands on windows EC2 instance to build windows docker images.
  for i in {1..60}; do
    instance_id=$(aws ec2 describe-instances \
      --filters "Name=tag:${WIN_EC2_TAG_KEY},Values=${WIN_EC2_TAG_VALUE}" | jq -r '.Reservations[0].Instances[0].InstanceId')
    if [[ "${instance_id}" == "null" ]]; then
      sleep 60
      continue
    fi
    instance_ping_status=$(aws ssm describe-instance-information \
      --filters "Key=InstanceIds,Values=${instance_id}" | jq -r '.InstanceInformationList[0].PingStatus')
    if [[ "${instance_ping_status}" == "Online" ]]; then
      # https://awscli.amazonaws.com/v2/documentation/api/latest/reference/ssm/send-command.html
      command_id=$(aws ssm send-command \
        --instance-ids "${instance_id}" \
        --document-name "${WIN_DOCKER_BUILD_SSM_DOCUMENT}" \
        --output-s3-bucket-name "${S3_FOR_WIN_DOCKER_IMG_BUILD}" \
        --output-s3-key-prefix 'runcommand' | jq -r '.Command.CommandId')
      # Export for checking command run status.
      export WINDOWS_DOCKER_IMG_BUILD_COMMAND_ID="${command_id}"
      echo "Windows ec2 is executing SSM command."
      return 0
    else
      echo "${i}: Current instance ping status: ${instance_ping_status}. Wait 1 minute to retry SSM command execution."
      sleep 60
    fi
  done
  echo "After 30 minutes, Windows ec2 is still not ready for SSM commands execution. Exit."
  return 1
}

function win_docker_img_build_status_check() {
  # Every 5 min, this function checks if the windows docker image build is finished successfully.
  # Normally, docker img build can take up to 1 hour. Here, we wait up to 30 * 5 min.
  for i in {1..30}; do
    # https://awscli.amazonaws.com/v2/documentation/api/latest/reference/ssm/list-commands.html
    command_run_status=$(aws ssm list-commands --command-id "${WINDOWS_DOCKER_IMG_BUILD_COMMAND_ID}" | jq -r '.Commands[0].Status')
    if [[ ${command_run_status} == 'Success' ]]; then
      echo "SSM command ${WINDOWS_DOCKER_IMG_BUILD_COMMAND_ID} finished successfully."
      return 0
    elif [[ ${command_run_status} == 'Failed' ]]; then
      echo "SSM command ${WINDOWS_DOCKER_IMG_BUILD_COMMAND_ID} failed."
      return 1
    else
      echo "${i}: Wait 5 min for build job finish."
      sleep 300
    fi
  done
  echo "SSM command ${WINDOWS_DOCKER_IMG_BUILD_COMMAND_ID} takes more time than expected."
  return 1
}

function build_win_docker_images() {
  local attempt=0

  while [[ ${attempt} -le ${MAX_RETRY} ]]; do
    attempt=$((attempt + 1))
    echo "Attempt ${attempt}"
    echo "Executing AWS SSM commands to build Windows docker images."
    if ! start_windows_img_build; then
      echo "Failed to start build, retrying ${attempt}/${MAX_RETRY}..."
      continue
    fi

    echo "Waiting for docker images creation. Building the docker images need to take 1 hour."
    # TODO(CryptoAlg-624): These image build may fail due to the Docker Hub pull limits made on 2020-11-01.
    if ! win_docker_img_build_status_check; then
        echo "Build failed, retrying ${attempt}/${MAX_RETRY}..."
        continue
    fi

    echo "Successfully built Windows docker images"
    return
  done

  echo "Failed to build Windows docker images"
}

while [[ $# -gt 0 ]]; do
  case ${1} in
  --build-type)
    BUILD_TYPE="${2}"
    shift
    ;;
  --platform)
    PLATFORM="${2}"
    shift
    ;;
  --project)
    PROJECT="${2}"
    shift
    ;;
  --max-retry)
    MAX_RETRY="${2}"
    shift
    ;;
  --timeout)
    TIMEOUT="${2}"
    shift
    ;;
  *)
    echo "${1} is not supported."
    exit 1
    ;;
  esac
  shift
done

MAX_RETRY=${MAX_RETRY:-0}
TIMEOUT=${TIMEOUT:-150}

if [[ -z ${BUILD_TYPE} ]]; then
  echo "No build type provided."
  exit 1
fi

assume_role

if [[ -z "${BUILD_TYPE+x}" || -z "${BUILD_TYPE}" ]]; then
  if [[ -z "${PLATFORM+x}" || -z "${PLATFORM}" ]]; then
      echo "When building Docker images, a platform must be specified"
      exit 1
  fi

  if [[ ${PLATFORM} == "linux" ]]; then
    build_linux_docker_images
  elif [[ ${PLATFORM} == "windows" ]]; then
    build_win_docker_images
  fi
  return
fi

if [[ ${BUILD_TYPE} == "ci" ]]; then
  if [[ -z "${PROJECT+x}" || -z "${PROJECT}" ]]; then
    echo "When building CI tests, a project name must be specified"
    exit 1
  fi

  build_codebuild_ci_project "${PROJECT}"
fi