# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

from aws_cdk import Stack, Environment
from aws_cdk import (
    pipelines,
    aws_codestarconnections as codestarconnections,
    aws_codebuild as codebuild,
    aws_iam as iam,
)
from aws_cdk.pipelines import CodeBuildStep, ShellStep
from constructs import Construct

from cdk.ci_stage import CiStage
from cdk.docker_image_build_stage import DockerImageBuildStage
from util.metadata import (
    AWS_ACCOUNT,
    AWS_REGION,
    GITHUB_REPO_NAME,
    GITHUB_REPO_OWNER,
    GITHUB_SOURCE_VERSION, PIPELINE_ACCOUNT, PIPELINE_REGION,
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

        cross_account_role = iam.Role(
            self,
            "CrossAccountCodeBuildRole",
            role_name="CrossAccountCodeBuildRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com")
        )

        cross_account_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                resources=[f'arn:aws:iam::{AWS_ACCOUNT}:role/CrossAccountCodeBuildRole'],
                actions=["sts:AssumeRole"],
            )
        )

        source = pipelines.CodePipelineSource.connection(
            f"{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}",
            "ci-pipeline",
            connection_arn=gh_connection.attr_connection_arn,
            code_build_clone_output=True,
        )

        commit_hash = source.source_attribute("CommitId")

        pipeline = pipelines.CodePipeline(
            self,
            "aws-lc-ci-pipeline",
            pipeline_name="aws-lc-ci-pipeline",
            cross_account_keys=True,
            synth=pipelines.ShellStep(
                "Synth",
                input=source,
                commands=[
                    "echo \"Environment variables:\"",
                    "env",
                    "npm install -g aws-cdk",
                    "cd tests/ci",
                    "python -m pip install -r requirements.txt",
                    "cd cdk",
                    "cdk synth",
                    # "git diff-tree --no-commit-id --name-only -r ${COMMIT_HASH}"
                ],
                env={
                    "CDK_DEPLOY_ACCOUNT": AWS_ACCOUNT,
                    "CDK_DEPLOY_REGION": AWS_REGION,
                    "GITHUB_REPO_OWNER": GITHUB_REPO_OWNER,
                    "GITHUB_REPO_NAME": GITHUB_REPO_NAME,
                    "GITHUB_SOURCE_VERSION": GITHUB_SOURCE_VERSION,
                    "PIPELINE_ACCOUNT": PIPELINE_ACCOUNT,
                    "PIPELINE_REGION": PIPELINE_REGION,
                    "PRE_PROD_ACCOUNT": AWS_ACCOUNT,
                    "PRE_PROD_REGION": AWS_REGION,
                    "COMMIT_HASH": commit_hash,
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
                    ),
                ],
                build_environment=codebuild.BuildEnvironment(
                    environment_variables={
                        "PIPELINE_ACCOUNT": codebuild.BuildEnvironmentVariable(value=PIPELINE_ACCOUNT),
                        "PIPELINE_REGION": codebuild.BuildEnvironmentVariable(value=PIPELINE_REGION),
                        "PRE_PROD_ACCOUNT": codebuild.BuildEnvironmentVariable(value=AWS_ACCOUNT),
                        "PRE_PROD_REGION": codebuild.BuildEnvironmentVariable(value=AWS_REGION),
                        # "GITHUB_REPO_OWNER": codebuild.BuildEnvironmentVariable(value=GITHUB_REPO_OWNER),
                        # "GITHUB_REPO_NAME": codebuild.BuildEnvironmentVariable(value=GITHUB_REPO_NAME),
                        # "GITHUB_SOURCE_VERSION": codebuild.BuildEnvironmentVariable(value=GITHUB_SOURCE_VERSION),
                    }
                ),
            )
        )

        docker_image_build_stage = DockerImageBuildStage(
            self,
            "Staging-DockerImageBuild",
            env=Environment(account=PIPELINE_ACCOUNT, region=PIPELINE_REGION)
        )

        pipeline.add_stage(
            docker_image_build_stage,
            post=[
                CodeBuildStep(
                    "StartDockerBuild",
                    commands=[
                        # "build_id=$(aws codebuild start-build-batch --project-name aws-lc-docker-image-build-linux | jq -r '.buildBatch.id')",
                        # "export AWS_LC_LINUX_BUILD_BATCH_ID='${build_id}'"
                        "echo \"Environment variables:\"",
                        "env",
                        'CREDENTIALS=$(aws sts assume-role --role-arn \"arn:aws:iam::${PRE_PROD_ACCOUNT}:role/CrossAccountCodeBuildRole\" --role-session-name codebuild-session)',
                        'export AWS_ACCESS_KEY_ID=$(echo $CREDENTIALS | jq -r .Credentials.AccessKeyId)',
                        'export AWS_SECRET_ACCESS_KEY=$(echo $CREDENTIALS | jq -r .Credentials.SecretAccessKey)',
                        'export AWS_SESSION_TOKEN=$(echo $CREDENTIALS | jq -r .Credentials.SessionToken)',
                        # "aws --region ${PRE_PROD_REGION} codebuild start-build-batch --project-name aws-lc-docker-image-build-linux --query 'build.id' --output text",
                    ],
                    # env={
                    #     "STACKS": docker_image_build_stage.stacks,
                    # },
                    role=cross_account_role
                ),
            ]
        )

        ci_stage = CiStage(
            self,
            "Staging-CiStage",
            env=Environment(account=PIPELINE_ACCOUNT, region=PIPELINE_REGION)
        )

        pipeline.add_stage(
            ci_stage,
            post=[
                ShellStep(
                    "RunIntegrationTests",
                    commands=[
                        "echo \"Environment variables:\"",
                        "env",
                    ],
                    role=cross_account_role
                ),
            ]
        )


