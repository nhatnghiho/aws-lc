# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

from aws_cdk import aws_ecr as ecr, aws_iam as iam
from constructs import Construct

from util.metadata import IS_DEV

class DockerEcrConstruct(Construct):
    """Define a stack of ECR to store pre-built Docker Images."""

    def __init__(self, scope: Construct, id: str, repo_name: str, **kwargs) -> None:
        super().__init__(scope, id)

        if IS_DEV:
            repo_name = f"{repo_name}-dev"

        self.ecr_repo = ecr.Repository(scope=self, id=id, repository_name=repo_name)

        self.ecr_repo.grant_pull_push(
            iam.ServicePrincipal("codebuild.amazonaws.com"))
