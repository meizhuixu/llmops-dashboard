# Terraform — Phase 4 Optional Stretch

This directory is a **stub placeholder** for Phase 4 infrastructure-as-code.

## Phase 4 Goal

Provision a production-grade Langfuse deployment on AWS using Terraform.

**Constraint**: `terraform plan` must pass. `terraform apply` is intentionally NOT run (cost control).

## Planned Module Structure

```
terraform/
├── main.tf              # Root module — wires together all child modules
├── variables.tf         # Input variables (region, instance sizes, domain)
├── outputs.tf           # Exported values (Langfuse URL, RDS endpoint)
├── versions.tf          # Provider version constraints
└── modules/
    ├── networking/      # VPC, subnets, security groups
    ├── ecs/             # ECS Fargate cluster + task definition for Langfuse
    ├── rds/             # RDS Postgres (Multi-AZ in prod)
    └── alb/             # Application Load Balancer + ACM cert
```

## Planned AWS Resources

| Resource | Purpose |
|----------|---------|
| VPC + subnets | Isolated network with public/private separation |
| ECS Fargate | Run `langfuse/langfuse` container without managing EC2 |
| RDS Postgres 16 | Managed database (replaces local docker postgres) |
| ALB | HTTPS termination + health checks |
| ACM | TLS certificate (auto-renewed) |
| Route53 | DNS record pointing to ALB |
| Secrets Manager | Store Langfuse NEXTAUTH_SECRET, SALT, DB password |
| CloudWatch | Log groups for ECS tasks |

## Estimated Monthly Cost (on-demand, us-east-1)

| Resource | Estimated |
|----------|-----------|
| ECS Fargate (0.5 vCPU / 1 GB) | ~$15/mo |
| RDS db.t4g.micro | ~$15/mo |
| ALB | ~$20/mo |
| **Total** | **~$50/mo** |

> Cost is why Phase 4 is optional stretch. Local docker compose serves all dev/demo needs at $0.

## How to Proceed (Phase 4)

1. Initialize providers: `terraform init`
2. Write module HCL, starting with `networking/`
3. Validate with `terraform plan -var-file=dev.tfvars`
4. Gate: CI must pass `terraform plan` with no errors before merging
5. **Do NOT run `terraform apply`** unless intentionally provisioning for real

## Prerequisites

- AWS CLI configured (`aws configure`)
- Terraform >= 1.6.0
- `LANGFUSE_SECRET_KEY` and related secrets pre-created in AWS Secrets Manager (or passed as vars)
