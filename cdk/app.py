#!/usr/bin/env python3
"""CDK app entry point for the Sumo Dashboard Viewer stack."""

import aws_cdk as cdk

from cdk.stacks.sumo_dashboard_viewer_stack import SumoDashboardViewerStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("aws_account_id"),
    region=app.node.try_get_context("aws_region") or "us-east-1",
)

SumoDashboardViewerStack(app, "SumoDashboardViewerStack", env=env)

app.synth()
