import pulumi
import pulumi_aws as aws

# Configuration
account_id = "443170140241"
provider_url = "https://token.actions.githubusercontent.com"
thumbprint = "6938fd4d98bab03faadb97b34396831e3780aea1"
audience = "sts.amazonaws.com"
repo_filter = "repo:Critiquely/*"

# Create GitHub OIDC provider
github_oidc_provider = aws.iam.OpenIdConnectProvider(
    "github_oidc_provider",
    url=provider_url,
    client_id_lists=[audience],
    thumbprint_lists=[thumbprint]
)

# Define trust policy document for GitHub Actions
assume_role_policy = aws.iam.get_policy_document(statements=[
    {
        "effect": "Allow",
        "principals": [{
            "type": "Federated",
            "identifiers": [f"arn:aws:iam::{account_id}:oidc-provider/token.actions.githubusercontent.com"]
        }],
        "actions": ["sts:AssumeRoleWithWebIdentity"],
        "conditions": [
            {
                "test": "StringLike",
                "variable": "token.actions.githubusercontent.com:sub",
                "values": [repo_filter],
            },
            {
                "test": "StringEquals",
                "variable": "token.actions.githubusercontent.com:aud",
                "values": [audience],
            },
        ]
    }
])

# Create IAM role for GitHub Actions
github_oidc_role = aws.iam.Role(
    "github_oidc_role",
    name="github_oidc",
    assume_role_policy=assume_role_policy.json,
    managed_policy_arns=[
        "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess"
    ]
)