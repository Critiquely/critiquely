import pulumi
import pulumi_aws as aws

ecr_name = "cli"

ecr = aws.ecr.Repository("cli",
    name=ecr_name,
    image_tag_mutability="MUTABLE",
    image_scanning_configuration={
        "scan_on_push": True,
    })

# Export the name of the bucket
pulumi.export('ecr_url', ecr.repository_url)
pulumi.export('ecr_name', ecr_name)