import json
import pulumi
import pulumi_aws as aws
import pulumi_aws_apigateway as apigateway
from ecr import ecr

# An execution role to use for the Lambda function
role = aws.iam.Role("webhook_fn_role", 
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com",
            },
        }],
    }),
    managed_policy_arns=[aws.iam.ManagedPolicy.AWS_LAMBDA_BASIC_EXECUTION_ROLE])

# A Lambda function to invoke
fn = aws.lambda_.Function("webhook_fn",
    runtime="python3.9",
    handler="handler.handler",
    role=role.arn,
    image_uri=ecr.repository_url)

# A REST API to route requests to HTML content and the Lambda function
api = apigateway.RestAPI("webhook_endpoint",
  routes=[
    apigateway.RouteArgs(path="/webhook", method=apigateway.Method.POST, event_handler=fn)
  ])

# The URL at which the REST API will be served.
pulumi.export("url", api.url)