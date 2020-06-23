from aws_cdk import (
    aws_ec2 as ec2,
    aws_logs as logs,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_rds as rds,
    aws_route53 as route53,
    aws_ecs_patterns as ecs_patterns,
    aws_certificatemanager as acm, 
    aws_secretsmanager as secretsmanager,
    aws_elasticloadbalancingv2 as elbv2,
    core
)

class KeycloakStack(core.Stack):

    def __init__(
        self, 
        scope: core.Construct, 
        id: str, 
        vpc: ec2.IVpc = None, 
        cluster: ecs.ICluster = None, 
        load_balancer: elbv2.IApplicationLoadBalancer = None, 
        log_group: logs.ILogGroup = None,
        keycloak_database_name: str = 'keykloak',
        keycloak_database_user: str = 'admin',
        **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # The code that defines your stack goes here
        
        keycloak_task_role = iam.Role(
            self, 'KeycloakTastRole',
            assumed_by=iam.ServicePrincipal('ecs-tasks.amazonaws.com')
        )

        keycloak_database_secret = secretsmanager.Secret(
            self, 'KeycloakDatabaseSecret',
            description='Keycloak Database Password',
            generate_secret_string=secretsmanager.SecretStringGenerator(exclude_punctuation=True)
        )

        keycloak_admin_username = secretsmanager.Secret(
            self, 'KeycloakAdminUsername',
            description='Keycloak Admin Name',
            generate_secret_string=secretsmanager.SecretStringGenerator(exclude_punctuation=True)
        )

        keycloak_admin_secret = secretsmanager.Secret(
            self, 'KeycloakAdminSecret',
            description='Keycloak Admin Password',
            generate_secret_string=secretsmanager.SecretStringGenerator(exclude_punctuation=True)
        )

        keycloak_database_cluster = rds.DatabaseCluster(
            self, 'KeycloakDatabaseCluster',
            engine= rds.DatabaseClusterEngine.AURORA,
            instance_props=rds.InstanceProps(
                instance_type=ec2.InstanceType.of(
                    instance_class=ec2.InstanceClass.BURSTABLE3, 
                    instance_size=ec2.InstanceSize.SMALL
                ),
                vpc=vpc,
            ),
            master_user= rds.Login(
                username=keycloak_database_user,
                password=keycloak_database_secret.secret_value,
            ),
            instances=1,
            default_database_name=keycloak_database_name,
            removal_policy=core.RemovalPolicy.DESTROY,
        )


        keycloak_hosted_zone = route53.HostedZone.from_lookup(
            self, 'KeycloakHostedZone',
            domain_name='florianpawlik.com'
        )

        keycloak_certificate = acm.DnsValidatedCertificate(
            self, 'KeycloakCertificate',
            hosted_zone=keycloak_hosted_zone,
            domain_name='keycloak.florianpawlik.com'
        )

        keycloak_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, 'KeycloakLoadBalancedFargateService',
            load_balancer=load_balancer,
            cluster=cluster,

            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_registry('jboss/keycloak:9.0.3'),
                container_port=8080,
                enable_logging=True,
                task_role=keycloak_task_role,

                log_driver=ecs.AwsLogDriver(
                    stream_prefix='keycloak',
                    log_group=log_group,
                ),

                secrets={
                    'DB_PASSWORD': ecs.Secret.from_secrets_manager(keycloak_database_secret),
                    'KEYCLOAK_PASSWORD': ecs.Secret.from_secrets_manager(keycloak_admin_secret),
                },
                
                environment={
                    'DB_VENDOR': 'mysql',
                    'DB_USER': keycloak_database_user,
                    'DB_ADDR': keycloak_database_cluster.cluster_endpoint.hostname,
                    'DB_DATABASE': keycloak_database_name,
                    # 'KEYCLOAK_LOGLEVEL': 'DEBUG',
                    'KEYCLOAK_USER': 'admin',
                    'PROXY_ADDRESS_FORWARDING': 'true',
                },
            ),

            memory_limit_mib=512,
            cpu=256,
            desired_count=1,
            public_load_balancer=True,
            domain_name= 'keycloak.florianpawlik.com',
            domain_zone= keycloak_hosted_zone,
            protocol=elbv2.ApplicationProtocol.HTTPS,
        )

        keycloak_service.target_group.enable_cookie_stickiness(core.Duration.seconds(24 * 60 * 60))
        keycloak_service.target_group.configure_health_check(
            port='8080',
            path='/auth/realms/master/.well-known/openid-configuration',
            timeout=core.Duration.seconds(20),
            healthy_threshold_count=2,
            unhealthy_threshold_count=10,
            interval=core.Duration.seconds(30),
        )

        keycloak_service.listener.add_certificates(
            'KeycloakListenerCertificate',
            certificates= [ keycloak_certificate ]
        )

        keycloak_database_cluster.connections.allow_default_port_from(keycloak_service.service, 'From Keycloak Fargate Service')

        core.CfnOutput(
            self, 'Output',
            value=keycloak_service.load_balancer.load_balancer_dns_name
        
        )
        # keycloak_task_definition = ecs.FargateTaskDefinition( 
        #     self, 'KeycloakTaskDefinition',
        #     cpu=256,
        #     memory_limit_mib=512,
        #     task_role=keycloak_task_role,            
        # )

        # keycloak_container = keycloak_task_definition.add_container(
        #     'keycloak_container',
        #     image=ecs.ContainerImage.from_registry('jboss/keycloak:9.0.3'),
        #     secrets={
        #         'DB_PASSWORD': ecs.Secret.from_secrets_manager(keycloak_database_secret),
        #         'KEYCLOAK_PASSWORD': ecs.Secret.from_secrets_manager(keycloak_admin_secret),
        #         'KEYCLOAK_USER': ecs.Secret.from_secrets_manager(keycloak_admin_username),
        #     },
        #     environment={
        #         'DB_VENDOR': 'mysql',
        #         'DB_USER': keycloak_database_user,
        #         'DB_ADDR': keycloak_database_cluster.cluster_endpoint.hostname,
        #         'DB_DATABASE': keycloak_database_name,
        #         'PROXY_ADDRESS_FORWARDING': 'true',
        #     },
        # )
        # keycloak_container.add_port_mappings(ecs.PortMapping(8080,80))

        # keycloak_fargate_service = ecs.FargateService(
        #     self, 'KeycloakFargateService',
        #     cluster=cluster,
        #     task_definition=keycloak_task_definition,
        #     desired_count=1,
        # )
        
        # keycloak_fargate_service.connections.allow_from(load_balancer, ec2.Port.tcp(80))
        # load_balancer.connections.allow_to(keycloak_fargate_service, ec2.Port.tcp(80))

        # elbv2.ApplicationTargetGroup(
        #     self, 'KeycloakFargateServiceTargetGroup',
        #     targets=[ keycloak_fargate_service ],
        #     protocol=elbv2.ApplicationProtocol.HTTP,
        #     vpc=vpc
        # )

        # load_balancer.co


        