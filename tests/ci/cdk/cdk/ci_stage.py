# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0 OR ISC

from aws_cdk import Stage, Environment
from constructs import Construct

from cdk.aws_lc_analytics_stack import AwsLcGitHubAnalyticsStack
from cdk.aws_lc_android_ci_stack import AwsLcAndroidCIStack
from cdk.aws_lc_ec2_test_framework_ci_stack import AwsLcEC2TestingCIStack
from cdk.aws_lc_github_ci_stack import AwsLcGitHubCIStack
from cdk.aws_lc_github_fuzz_ci_stack import AwsLcGitHubFuzzCIStack
from util.metadata import AWS_ACCOUNT, AWS_REGION


class CiStage(Stage):
    def __init__(
            self,
            scope: Construct,
            id,
            **kwargs
    ):
        super().__init__(
            scope,
            id,
            **kwargs,
        )

        env=Environment(account=AWS_ACCOUNT, region=AWS_REGION)

        x86_build_spec_file = "cdk/codebuild/github_ci_linux_x86_omnibus.yaml"
        AwsLcGitHubCIStack(self, "aws-lc-ci-linux-x86", x86_build_spec_file, env=env)
        arm_build_spec_file = "cdk/codebuild/github_ci_linux_arm_omnibus.yaml"
        AwsLcGitHubCIStack(self, "aws-lc-ci-linux-arm", arm_build_spec_file, env=env)
        integration_build_spec_file = "cdk/codebuild/github_ci_integration_omnibus.yaml"
        AwsLcGitHubCIStack(self, "aws-lc-ci-integration", integration_build_spec_file, env=env)
        win_x86_build_spec_file = "cdk/codebuild/github_ci_windows_x86_omnibus.yaml"
        AwsLcGitHubCIStack(self, "aws-lc-ci-windows-x86", win_x86_build_spec_file, env=env)
        fuzz_build_spec_file = "cdk/codebuild/github_ci_fuzzing_omnibus.yaml"
        AwsLcGitHubFuzzCIStack(self, "aws-lc-ci-fuzzing", fuzz_build_spec_file, env=env)
        analytics_build_spec_file = "cdk/codebuild/github_ci_analytics_omnibus.yaml"
        AwsLcGitHubAnalyticsStack(self, "aws-lc-ci-analytics", analytics_build_spec_file, env=env)
        # bm_framework_build_spec_file = "cdk/codebuild/bm_framework_omnibus.yaml"
        # BmFrameworkStack(app, "aws-lc-ci-bm-framework", bm_framework_build_spec_file, env=env)
        ec2_test_framework_build_spec_file = "cdk/codebuild/ec2_test_framework_omnibus.yaml"
        AwsLcEC2TestingCIStack(self, "aws-lc-ci-ec2-test-framework", ec2_test_framework_build_spec_file, env=env)
        android_build_spec_file = "cdk/codebuild/github_ci_android_omnibus.yaml"
        AwsLcAndroidCIStack(self, "aws-lc-ci-devicefarm-android", android_build_spec_file, env=env)


