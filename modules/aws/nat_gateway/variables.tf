# EIP
variable "existing_eip_id" {
  description = "An existing EIP that allocate to the Nat Gateway."
  type        = string
  default     = null
}

variable "public_ipv4_pool" {
  description = "EC2 IPv4 address pool identifier or amazon."
  type        = string
  default     = "amazon"
}

variable "domain" {
  description = "Indicates if this EIP is for use in VPC. Defaults to vpc."
  type        = string
  default     = "vpc"
}

variable "customer_owned_ipv4_pool" {
  description = "ID of a customer-owned address pool. "
  type        = string
  default     = null
}

# Nat Gateway
variable "allocate_eip" {
  description = "Boolean whether allocate an EIP to the Nat Gateway. Default is true."
  type        = bool
  default     = true
}

variable "connectivity_type" {
  description = "Connectivity type for the gateway. Valid values are private and public. Defaults to public."
  type        = string
  default     = "public"
}

variable "subnet_id" {
  description = " The Subnet ID of the subnet in which to place the gateway."
  type        = string
}

variable "private_ip" {
  description = "The private IPv4 address to assign to the NAT gateway. If you don't provide an address, a private IPv4 address will be automatically assigned."
  type        = string
  default     = null
}

## Tag related
variable "tags" {
  description = <<-EOF
  Tags that applies to related resources.
  Format:
  ```
    tags = {
        \<Option\> = \<Option value\>
    }
  ```
  Options:
    - general :  Tags will add to all resources.
    - eip     :  Tags for Elastic IP.
    - ngw     :  Tags for Nat Gatway.
    
  Example:
  ```
  tags = {
    general = {
      Created_from = "Terraform"
    },
    ngw = {
      Used_to = "ASG"
    }
  }
  ```
  EOF

  default = {}
  type    = map(map(string))
  validation {
    condition = var.tags == null ? true : alltrue([
      for k, v in var.tags : contains([
        "general",
        "eip",
        "ngw"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: general, eip, ngw."
  }
}