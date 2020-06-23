from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_logs as logs,
    aws_elasticloadbalancingv2 as elbv2,
    core
)


class ServiceStack(core.Stack):

    @property
    def vpc(self):
        return self._vpc

    @property
    def cluster(self):
        return self._cluster

    @property
    def load_balancer(self):
        return self._load_balancer

    @property
    def log_group(self):
        return self._log_group

    

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # The code that defines your stack goes here

        self._vpc=ec2.Vpc(
            self, 'ServiceVpc',
        )

        self._cluster=ecs.Cluster(
            self, 'ServiceCluster',
            vpc=self.vpc
        )

        self._load_balancer=elbv2.ApplicationLoadBalancer(
            self, 'ServiceLoadbalancer',
            vpc=self.vpc,
            internet_facing=True,
        )

        self._log_group=logs.LogGroup(
            self, 'ServiceLogGroup',
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=core.RemovalPolicy.DESTROY
        )