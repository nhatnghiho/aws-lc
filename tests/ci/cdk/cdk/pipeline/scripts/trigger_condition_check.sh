#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

set -exuo pipefail

export NEED_REBUILD=${NEED_REBUILD:-0}
LINUX_DOCKER_PATHS="tests/ci/docker_images/(dependencies|linux)"
WINDOWS_DOCKER_PATHS="tests/ci/docker_images/windows"

function assume_role() {
  CREDENTIALS=$(aws sts assume-role --role-arn arn:aws:iam::${DEPLOY_ACCOUNT}:role/CrossAccountCodeBuildRole --role-session-name codebuild-session)
  export AWS_ACCESS_KEY_ID=$(echo $CREDENTIALS | jq -r .Credentials.AccessKeyId)
  export AWS_SECRET_ACCESS_KEY=$(echo $CREDENTIALS | jq -r .Credentials.SecretAccessKey)
  export AWS_SESSION_TOKEN=$(echo $CREDENTIALS | jq -r .Credentials.SessionToken)
}

function check_pipeline_trigger_type() {
  trigger_type=$(aws codepipeline get-pipeline-execution \
                     --pipeline-name aws-lc-ci-pipeline \
                     --pipeline-execution-id ${PIPELINE_EXECUTION_ID})
  if (echo "$trigger_type" | jq -e '.pipelineExecution.trigger.triggerType != "Webhook"'); then
    NEED_REBUILD=$((NEED_REBUILD + 1))
  fi
}

function get_commit_changed_files() {
  local file_paths
  if [[ ${PLATFORM} == "linux" ]]; then
    file_paths=${LINUX_DOCKER_PATHS}
  elif [[ ${PLATFORM} == "windows" ]]; then
    file_paths=${WINDOWS_DOCKER_PATHS}
  fi

  changed_files=$(git diff-tree --no-commit-id --name-only -r ${COMMIT_HASH})

  if (echo "$changed_files" | grep -E $file_paths); then
    NEED_REBUILD=$((NEED_REBUILD + 1))
  fi
}

function get_cfn_changeset() {
  for stack in ${STACKS}; do
    changes_count=$(aws cloudformation describe-change-set \
                          --change-set-name PipelineChange \
                          --stack-name "${stack}" | jq '.Changes | length')
    if [ "$changes_count" -gt 0 ]; then
      NEED_REBUILD=$((NEED_REBUILD + 1))
      break
    fi
  done
}

#function check_last_build_time() {
#  build_id=$(aws codebuild list-builds-for-project \
#      --project-name YOUR_PROJECT_NAME \
#      --sort-order DESCENDING \
#      --filter '{"status":["SUCCEEDED"]}' \
#      --max-items 1)
#
#  # Then get the detailed build information using the build ID
#  last_build_time=$(aws --region ${DEPLOY_REGION} codebuild batch-get-builds --ids ${build_id} | jq -r '.builds[0].startTime')
#  if [ "$last_build_time" == "null" ]; then
#    echo "Build not found, assuming it's the first build"
#    NEED_REBUILD+=1
#  fi
#}

echo \"Environment variables:\"
env

while [[ $# -gt 0 ]]; do
  case ${1} in
  --stacks)
    STACKS="${2}"
    shift
    ;;
  --build-type)
    BUILD_TYPE="${2}"
    shift
    ;;
  --platform)
    PLATFORM="${2}"
    shift
    ;;
  *)
    echo "${1} is not supported."
    exit 1
    ;;
  esac
  shift
done

if [[ -z "${BUILD_TYPE+x}" || -z "${BUILD_TYPE}" ]]; then
  echo "No build type provided."
  exit 1
fi

if [[ -z "${STACKS+x}"  || -z "${STACKS}" ]]; then
  echo "No stacks provided."
  exit 1
fi

if [[ ${BUILD_TYPE} == "docker" ]]; then
  if [[ -z "${PLATFORM+x}" || -z "${PLATFORM}" ]]; then
      echo "A platform must be specified"
      exit 1
  fi

  check_pipeline_trigger_type

  assume_role
  get_commit_changed_files
  get_cfn_changeset
  return
fi

if [[ ${BUILD_TYPE} == "ci" ]]; then
  assume_role
  get_cfn_changeset
fi