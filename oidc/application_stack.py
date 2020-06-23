from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_logs as logs,
    aws_route53 as route53,
    aws_certificatemanager as acm,
    aws_elasticloadbalancingv2 as elbv2,
    core
)

class ApplicationStack(core.Stack):

    def __init__(
        self, 
        scope: core.Construct, 
        id: str, 

        domain_name: str,

        identity_provider_client_id: str,
        identity_provider_client_secret: str,
        identity_provider_client_url: str,
        identity_provider_realm: str,
        identity_provider_scope: str = 'openid',
        
        vpc: ec2.IVpc = None, 
        cluster: ecs.ICluster = None, 
        load_balancer: elbv2.IApplicationLoadBalancer = None, 
        log_group: logs.ILogGroup = None,
        **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # The code that defines your stack goes here
        
        if vpc is None:
            vpc = ec2.Vpc(
                self, 'ApplicationkVpc'
            )

        if cluster is None:
            cluster = ecs.Cluster(
                self, 'ApplicationCluster',
                vpc=vpc
            )
        
        if log_group is None:
            log_group = logs.LogGroup(       
                self, 'ApplicationLogGroup',
                retention=logs.RetentionDays.ONE_WEEK,
                removal_policy=core.RemovalPolicy.DESTROY
            )

        application_task_role = iam.Role(
            self, 'ApplicationTaskRole',
            assumed_by=iam.ServicePrincipal('ecs-tasks.amazonaws.com')
        )

        application_hosted_zone = route53.HostedZone.from_lookup(
            self, 'ApplicationHostedZone',
            domain_name=domain_name
        )

        application_certificate = acm.DnsValidatedCertificate(
            self, 'FrontendAlbCertificate',
            hosted_zone=application_hosted_zone,
            domain_name='app.' + domain_name
        )

        application_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, 'ApplicationLoadBalancedFargateService',
            cluster=cluster,
            load_balancer=load_balancer,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset("application"),
                enable_logging=True,
                log_driver=ecs.AwsLogDriver(
                    stream_prefix='application',
                    log_group=log_group
                ),
                task_role=application_task_role,
                container_port=8080,
                
            ),
            memory_limit_mib=512,
            cpu=256,
            desired_count=1,
            public_load_balancer=True,
            domain_name='app.' + domain_name,
            domain_zone=application_hosted_zone,
            protocol=elbv2.ApplicationProtocol.HTTPS,
        )

        application_service.target_group.enable_cookie_stickiness(core.Duration.seconds(24 * 60 * 60))
        application_service.target_group.configure_health_check(
            port='8080',
            path='/',
            timeout=core.Duration.seconds(20),
            healthy_threshold_count=2,
            unhealthy_threshold_count=10,
            interval=core.Duration.seconds(30),
        )
       
        application_service.listener.add_certificates(
            'ApplicationServiceCertificate',
            certificates=[ application_certificate ]
        )

        application_service.listener.add_action(
            'DefaultAction',
            action=elbv2.ListenerAction.authenticate_oidc(
                authorization_endpoint=identity_provider_client_url + '/auth/realms/' + identity_provider_realm +'/protocol/openid-connect/auth',
                token_endpoint=identity_provider_client_url + '/auth/realms/' + identity_provider_realm +'/protocol/openid-connect/token',
                user_info_endpoint=identity_provider_client_url + '/auth/realms/' + identity_provider_realm +'/protocol/openid-connect/userinfo',
                issuer=identity_provider_client_url + '/auth/realms/' + identity_provider_realm,
                client_id=identity_provider_client_id,
                client_secret=core.SecretValue(identity_provider_client_secret),
                scope=identity_provider_scope,
                on_unauthenticated_request=elbv2.UnauthenticatedAction.AUTHENTICATE,
                next=elbv2.ListenerAction.forward([application_service.target_group]),
            )
        )

        application_service.load_balancer.connections.allow_to_any_ipv4(
            port_range= ec2.Port(
                from_port=443,
                to_port=443,
                protocol=ec2.Protocol.TCP,
                string_representation='Allow ALB to verify token'
            )
        )
