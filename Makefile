.PHONY: help init plan apply destroy clean validate fmt

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

init: ## Initialize Terraform
	cd infra && terraform init

validate: ## Validate Terraform configuration
	cd infra && terraform validate

fmt: ## Format Terraform files
	cd infra && terraform fmt -recursive

plan: ## Run Terraform plan for dev environment
	cd infra && terraform plan -var-file=../envs/dev/terraform.tfvars

apply: ## Apply Terraform for dev environment
	cd infra && terraform apply -var-file=../envs/dev/terraform.tfvars

destroy: ## Destroy Terraform infrastructure for dev environment
	cd infra && terraform destroy -var-file=../envs/dev/terraform.tfvars

clean: ## Clean Terraform files
	rm -rf infra/.terraform
	rm -f infra/.terraform.lock.hcl
	rm -f infra/terraform.tfstate*
