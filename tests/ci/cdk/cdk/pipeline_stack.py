# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

from aws_cdk import Stack, Environment
from aws_cdk import (
    pipelines,
    aws_codestarconnections as codestarconnections,
    aws_iam as iam,
)
from aws_cdk.pipelines import CodeBuildStep, ShellStep
from constructs import Construct

from cdk.docker_image_build_stage import DockerImageBuildStage
from util.metadata import (
    AWS_ACCOUNT,
    AWS_REGION,
    GITHUB_REPO_NAME,
    GITHUB_REPO_OWNER,
    GITHUB_SOURCE_VERSION,
)

from aws_cdk.aws_codepipeline_actions import ManualApprovalAction


class AwsLcCiPipeline(Stack):
    def __init__(
            self,
            scope: Construct,
            id: str,
            **kwargs,
    ) -> None:
        super().__init__(
            scope,
            id,
            **kwargs,
        )

        gh_connection = codestarconnections.CfnConnection(
            self,
            "GitHubConnection",
            connection_name="AwsLcCiPipelineGitHubConnection",
            provider_type="GitHub",
        )

        pipeline = pipelines.CodePipeline(
            self,
            "Pipeline",
            synth=pipelines.ShellStep(
                "Synth",
                input=pipelines.CodePipelineSource.connection(
                    f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}",
                    "ci-pipeline",
                    connection_arn=gh_connection.attr_connection_arn,
                ),
                commands=[
                    "echo \"Environment variables:\"",
                    "env",
                    "npm install -g aws-cdk",
                    "cd tests/ci",
                    "python -m pip install -r requirements.txt",
                    "cd cdk",
                    "cdk synth",
                ],
                env={
                    "CDK_DEPLOY_ACCOUNT": AWS_ACCOUNT,
                    "CDK_DEPLOY_REGION": AWS_REGION,
                    "GITHUB_REPO_OWNER": GITHUB_REPO_OWNER,
                    "GITHUB_REPO_NAME": GITHUB_REPO_NAME,
                    "GITHUB_SOURCE_VERSION": GITHUB_SOURCE_VERSION,
                },
                primary_output_directory="tests/ci/cdk/cdk.out",
            ),
            self_mutation=True,
            code_build_defaults=pipelines.CodeBuildOptions(
                role_policy=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        resources=["*"],
                        actions=["sts:AssumeRole"],
                        conditions={
                            "StringEquals": {
                                "iam:ResourceTag/aws-cdk:bootstrap-role": "lookup",
                            }
                        }
                    )
                ]
            )
        )

        docker_image_build_stage = DockerImageBuildStage(
            self,
            "Staging-DockerImageBuild",
            env=Environment(account=AWS_ACCOUNT, region=AWS_REGION)
        )

        pipeline.add_stage(
            docker_image_build_stage,
            post=[
                ShellStep(
                    "StartDockerBuild",
                    commands=[
                        # "build_id=$(aws codebuild start-build-batch --project-name aws-lc-docker-image-build-linux | jq -r '.buildBatch.id')",
                        # "export AWS_LC_LINUX_BUILD_BATCH_ID='${build_id}'"
                        "echo \"Environment variables:\"",
                        "env"
                    ],
                ),
            ]
        )


