#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

set -exuo pipefail

source util.sh

PROD_ACCOUNT="620771051181"
PRE_PROD_ACCOUNT="351119683581"

PROD_ACCOUNT_ARN="arn:aws:iam::${PROD_ACCOUNT}:role/CrossAccountBuildRole"
PRE_PROD_ACCOUNT_ARN="arn:aws:iam::${PRE_PROD_ACCOUNT}:role/CrossAccountBuildRole"

function copy_images() {
  # JSON arrays with repo, tag, manifest, media_type
  manifest_data=()

  assume_role "$PRE_PROD_ACCOUNT_ARN"

  # Gather all image manifests
  for repo in $REPOS; do
    echo "Checking repo: $repo"
    tags=$(aws ecr list-images \
      --repository-name "$repo" \
      --filter tagStatus=TAGGED \
      | jq -r '.imageIds[].imageTag' | grep '_latest$' || true)

    for tag in $tags; do
      echo "Fetching image manifest for $repo:$tag"
      image_data=$(aws ecr batch-get-image \
        --repository-name "$repo" \
        --image-ids imageTag="$tag" \
        --query 'images[0]' \
        --output json)

      manifest=$(echo "$image_data" | jq -r .imageManifest)
      media_type=$(echo "$image_data" | jq -r .imageManifestMediaType)

      # Append as a JSON string to the list
      manifest_data+=("$(jq -n \
        --arg repo "$repo" \
        --arg tag "$tag" \
        --arg manifest "$manifest" \
        --arg media_type "$media_type" \
        '{repo: $repo, tag: $tag, manifest: $manifest, media_type: $media_type}')")
    done
  done

  assume_role "$PROD_ACCOUNT_ARN"

  # Push all manifests prod
  for item in "${manifest_data[@]}"; do
    repo=$(echo "$item" | jq -r .repo)
    latest_tag=$(echo "$item" | jq -r .tag)
    manifest=$(echo "$item" | jq -r .manifest)
    media_type=$(echo "$item" | jq -r .media_type)

    img_push_date=$(date +%Y-%m-%d)

    if [[ -n "${PLATFORM:-}" && ${PLATFORM} == "windows" ]]; then
      img_push_date=$(date +%Y-%m-%d-%H)
    fi

    date_tag="${tag%_latest}_${img_push_date}"

    aws ecr put-image \
      --repository-name "$repo" \
      --image-tag "$latest_tag" \
      --image-manifest "$manifest" \
      --image-manifest-media-type "$media_type"

    aws ecr put-image \
      --repository-name "$repo" \
      --image-tag "$date_tag" \
      --image-manifest "$manifest" \
      --image-manifest-media-type "$media_type"
  done

  echo "Successfully copied images from pre-prod to prod"
}

while [[ $# -gt 0 ]]; do
  case ${1} in
  --repos)
    REPOS="${2}"
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

if [[ -z "${REPOS:+x}" ]]; then
  echo "No build type provided."
  exit 1
fi

copy_images
