#!/usr/bin/env python3
import os

from aws_cdk import core

from oidc.service_stack import ServiceStack
from oidc.keycloak_stack import KeycloakStack
from oidc.application_stack import ApplicationStack


app = core.App()

environment = core.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"],
    region=os.environ["CDK_DEFAULT_REGION"]
)


service = ServiceStack(app, 'service', env=environment)

KeycloakStack(
    app, 'keycloak', 
    
    vpc=service.vpc, 
    cluster=service.cluster, 
    log_group=service.log_group,
    
    env=environment
)

ApplicationStack(
    app, 'application', 

    domain_name= os.environ['CDK_APP_DOMAIN'],

    identity_provider_client_id= os.environ['CDK_APP_IDP_CLIENT_ID', 'my_app'],
    identity_provider_client_secret=os.environ['CDK_APP_IDP_CLIENT_SECRET'],
    identity_provider_client_url=os.environ['CDK_APP_IDP_CLIENT_URL'],
    identity_provider_realm=os.environ['CDK_APP_IDP_CLIENT_REALM'],
    identity_provider_scope=os.environ['CDK_APP_IDP_CLIENT_SCOPE', 'openid'],

    vpc=service.vpc, 
    cluster=service.cluster, 
    log_group=service.log_group,

    env=environment
)

app.synth()