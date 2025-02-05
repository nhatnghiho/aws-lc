#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

set -exuo pipefail

# -e: Exit on any failure
# -x: Print the command before running
# -u: Any variable that is not set will cause an error if used
# -o pipefail: Makes sure to exit a pipeline with a non-zero error code if any command in the pipeline exists with a
#              non-zero error code.

function delete_s3_buckets() {
  aws s3api list-buckets --query "Buckets[].Name" | jq '.[]' | while read -r i; do
    bucket_name=$(echo "${i}" | tr -d '"')
    # Delete the bucket if its name uses AWS_LC_S3_BUCKET_PREFIX.
    if [[ "${bucket_name}" == *"${AWS_LC_S3_BUCKET_PREFIX}"* ]]; then
      aws s3 rm "s3://${bucket_name}" --recursive
      aws s3api delete-bucket --bucket "${bucket_name}"
    # Delete bm-framework buckets if we're not on the team account
    elif [[ "${CDK_DEPLOY_ACCOUNT}" != "620771051181" ]] && [[ "${bucket_name}" == *"${aws-lc-ci-bm-framework}"* ]]; then
      aws s3 rm "s3://${bucket_name}" --recursive
      aws s3api delete-bucket --bucket "${bucket_name}"
    fi
  done
}

function delete_container_repositories() {
  ecr_repos=$(aws ecr describe-repositories)
  if [[ "${ecr_repos}" == *"${ECR_LINUX_AARCH_REPO_NAME}"* ]]; then
    aws ecr delete-repository --repository-name "${ECR_LINUX_AARCH_REPO_NAME}" --force
  fi
  if [[ "${ecr_repos}" == *"${ECR_LINUX_X86_REPO_NAME}"* ]]; then
    aws ecr delete-repository --repository-name "${ECR_LINUX_X86_REPO_NAME}" --force
  fi
  if [[ "${ecr_repos}" == *"${ECR_WINDOWS_X86_REPO_NAME}"* ]]; then
    aws ecr delete-repository --repository-name "${ECR_WINDOWS_X86_REPO_NAME}" --force
  fi
}

function destroy_ci() {
  if [[ "${CDK_DEPLOY_ACCOUNT}" == "620771051181" ]]; then
    echo "destroy_ci should not be executed on team account."
    exit 1
  fi
  cdk destroy 'aws-lc-*' --force
  # CDK stack destroy does not delete s3 bucket automatically.
  delete_s3_buckets
  # CDK stack destroy does not delete ecr automatically.
  delete_container_repositories
}

function destroy_docker_img_build_stack() {
  if [[ "${IMG_BUILD_STATUS}" == "Failed" ]]; then
    echo "Docker images build failed. AWS resources of building Docker images is kept for debug."
    exit 1
  fi
  # Destroy all temporary resources created for all docker image build.
  cdk destroy 'aws-lc-docker-image-build-*' --force
  # CDK stack destroy does not delete s3 bucket automatically.
  delete_s3_buckets
}

function export_global_variables() {
  # If these variables are not set or empty, defaults are export.
  if [[ -z "${CDK_DEPLOY_ACCOUNT+x}" || -z "${CDK_DEPLOY_ACCOUNT}" ]]; then
    export CDK_DEPLOY_ACCOUNT='620771051181'
  fi
  if [[ -z "${CDK_DEPLOY_REGION+x}" || -z "${CDK_DEPLOY_REGION}" ]]; then
    export CDK_DEPLOY_REGION='us-west-2'
    export AWS_DEFAULT_REGION="${CDK_DEPLOY_REGION}"
  fi
  if [[ -z "${GITHUB_REPO_OWNER+x}" || -z "${GITHUB_REPO_OWNER}" ]]; then
    export GITHUB_REPO_OWNER='aws'
  fi
  if [[ -z "${GITHUB_SOURCE_VERSION+x}" || -z "${GITHUB_SOURCE_VERSION}" ]]; then
    export GITHUB_SOURCE_VERSION='main'
  fi
  # Other variables for managing resources.
  DATE_NOW="$(date +%Y-%m-%d-%H-%M)"
  export GITHUB_REPO='aws-lc'
  export ECR_LINUX_AARCH_REPO_NAME='aws-lc-docker-images-linux-aarch'
  export ECR_LINUX_X86_REPO_NAME='aws-lc-docker-images-linux-x86'
  export ECR_WINDOWS_X86_REPO_NAME='aws-lc-docker-images-windows-x86'
  export AWS_LC_S3_BUCKET_PREFIX='aws-lc-windows-docker-image-build-s3'
  export S3_FOR_WIN_DOCKER_IMG_BUILD="${AWS_LC_S3_BUCKET_PREFIX}-${DATE_NOW}"
  export WIN_EC2_TAG_KEY='aws-lc'
  export WIN_EC2_TAG_VALUE="aws-lc-windows-docker-image-build-${DATE_NOW}"
  export WIN_DOCKER_BUILD_SSM_DOCUMENT="windows-ssm-document-${DATE_NOW}"
  export IMG_BUILD_STATUS='unknown'
  # 620771051181 is AWS-LC team AWS account.
  if [[ "${CDK_DEPLOY_ACCOUNT}" != "620771051181" ]] && [[ "${GITHUB_REPO_OWNER}" == 'aws' ]]; then
    echo "Only team account is allowed to create CI stacks on aws repo."
    exit 1
  fi
}
export_global_variables