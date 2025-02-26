# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC
from typing import Mapping

import jsii
from aws_cdk import (
    pipelines,
    aws_codepipeline_actions as cp_actions,
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_iam as iam
)

from util.metadata import GITHUB_REPO_OWNER, GITHUB_REPO_NAME, GITHUB_SOURCE_VERSION


@jsii.implements(pipelines.ICodePipelineActionFactory)
class DockerBuildStep(pipelines.Step):
    def __init__(self,
                 id,
                 name_prefix,
                 # input: pipelines.IFileSetProducer,
                 input: pipelines.FileSet,
                 stacks: list[str],
                 role: iam.Role,
                 platform: str="",
                 max_retry: int=0,
                 timeout: int=150,
                 env: dict[str, any]=None):
        super().__init__(id)

        # self._discover_referenced_outputs({
        #     "env": {}
        # })

        self.name_prefix = name_prefix
        self.input = input
        self.platform = platform
        self.stacks = stacks
        self.role = role
        self.max_retry = max_retry
        self.timeout = timeout
        self.env = {
            key: codebuild.BuildEnvironmentVariable(value=value)
            for key, value in env.items()
        }

    @jsii.member(jsii_name="produceAction")
    def produce_action(self,
                       stage: codepipeline.IStage,
                       *,
                       scope,
                       action_name,
                       run_order,
                       variables_namespace=None,
                       artifacts: pipelines.ArtifactMap,
                       fallbackArtifact=None,
                       pipeline: pipelines.CodePipeline,
                       codeBuildDefaults=None,
                       beforeSelfMutation=None,
                       stack_outputs_map: pipelines.StackOutputsMap):

        docker_build_project = codebuild.PipelineProject(
            scope,
            f"{self.name_prefix}-DockerImageBuild",
            build_spec=codebuild.BuildSpec.from_object({
                "version": "0.2",
                "env": {
                    "exported-variables": [
                        "NEED_REBUILD"
                    ]
                },
                "phases": {
                    "build": {
                        "commands": [
                            "cd tests/ci/cdk/cdk/pipeline/scripts",
                            "chmod +x trigger_condition_check.sh",
                            "chmod +x build_target.sh",
                            "./trigger_condition_check.sh --build-type docker --platform ${PLATFORM} --stacks \"${STACKS}\"",
                            "./build_target.sh --build-type docker --platform ${PLATFORM} --max-retry ${MAX_RETRY} --timeout ${TIMEOUT}"
                        ]
                    }
                }
            }),
            role=self.role,
            project_name=f"{self.name_prefix}-DockerImageBuild"
        )

        docker_build_action = cp_actions.CodeBuildAction(
            action_name=f"{self.name_prefix}-DockerImageBuild",
            # input=artifacts.to_code_pipeline(self.input.primary_output),
            input=artifacts.to_code_pipeline(self.input),
            run_order=run_order,
            project=docker_build_project,
            environment_variables={
                **self.env,
                "PLATFORM": codebuild.BuildEnvironmentVariable(value=self.platform),
                "STACKS": codebuild.BuildEnvironmentVariable(value=" ".join(self.stacks)),
                "MAX_RETRY": codebuild.BuildEnvironmentVariable(value=self.max_retry),
                "TIMEOUT": codebuild.BuildEnvironmentVariable(value=self.timeout),
            },
            outputs=[codepipeline.Artifact()],
            # variables_namespace=f'{self.name_prefix}-DockerImageBuild',
            variables_namespace=f'{self.name_prefix}-DockerImageBuild',
        )

        stage.add_action(docker_build_action)

        return pipelines.CodePipelineActionFactoryResult(
            run_orders_consumed=1
        )
