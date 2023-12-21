## Transit gateway
variable "existing_tgw" {
  description = <<-EOF
    Using existing Transit gateway. 
    If the id is specified, will use this Transit gateway ID. Otherwise, will search the Transit gateway based on the given infomation.
    Options:
        - id     :  (Optional|string) ID of the specific Transit gateway.
        - filter :  (Optional|map) Map of the filters. Value should be a list.     
    Example:
    ```
    existing_tgw = {
        filter = {
            "options.amazon-side-asn" = ["64512"]
        }
    }
    ```
    EOF
  type        = any
  default     = null
  validation {
    condition = var.existing_tgw == null ? true : alltrue([
      for k, v in var.existing_tgw : contains([
        "id",
        "filter"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: id, filter."
  }
}

variable "tgw_name" {
  description = "Transit gateway name"
  default     = ""
  type        = string
}

variable "amazon_side_asn" {
  description = "Private Autonomous System Number (ASN) for the Amazon side of a BGP session. The range is 64512 to 65534 for 16-bit ASNs and 4200000000 to 4294967294 for 32-bit ASNs. Default value: 64512."
  default     = "64512"
  type        = string
}

variable "auto_accept_shared_attachments" {
  description = "Whether resource attachment requests are automatically accepted. Valid values: disable, enable. Default value: disable."
  default     = "disable"
  type        = string
}

variable "default_route_table_association" {
  description = "Whether resource attachments are automatically associated with the default association route table. Valid values: disable, enable. Default value: enable."
  default     = "enable"
  type        = string
}

variable "default_route_table_propagation" {
  description = "Whether resource attachments automatically propagate routes to the default propagation route table. Valid values: disable, enable. Default value: enable."
  default     = "enable"
  type        = string
}

variable "vpn_ecmp_support" {
  description = "Whether VPN Equal Cost Multipath Protocol support is enabled. Valid values: disable, enable. Default value: enable."
  default     = "enable"
  type        = string
}

variable "dns_support" {
  description = "Whether DNS support is enabled. Valid values: disable, enable. Default value: enable."
  default     = "enable"
  type        = string
}

variable "tgw_description" {
  description = "Description of the EC2 Transit Gateway."
  default     = ""
  type        = string
}

## Transit gateway attachment
variable "tgw_attachments" {
  description = <<-EOF
    Transit gateway VPC attachments for the Transit gateway. 
    Format:
    ```
        tgw_attachments = {
            \<Attachment name\> = {
                subnet_ids         = \<Subnet_id\>  
                transit_gateway_id = \<Transit_gateway_id\>
                vpc_id             = \<VPC_id\> 
                \<Option\> = \<Option value\>
            }
        }
    ```
    Options:
        - subnet_ids                                      : (Required|list) Identifiers of EC2 Subnets.
        - vpc_id                                          : (Required|string) Identifier of EC2 VPC.
        - appliance_mode_support                          : (Optional|string) Whether Appliance Mode support is enabled. If enabled, a traffic flow between a source and destination uses the same Availability Zone for the VPC attachment for the lifetime of that flow. Valid values: disable, enable. Default value: disable.
        - dns_support                                     : (Optional|string) Whether DNS support is enabled. Valid values: disable, enable. Default value: enable.
        - ipv6_support                                    : (Optional|string) Whether IPv6 support is enabled. Valid values: disable, enable. Default value: disable.
        - transit_gateway_default_route_table_association : (Optional|bool) Boolean whether the VPC Attachment should be associated with the EC2 Transit Gateway association default route table. This cannot be configured or perform drift detection with Resource Access Manager shared EC2 Transit Gateways. Default value: true.
        - transit_gateway_default_route_table_propagation : (Optional|bool) Boolean whether the VPC Attachment should propagate routes with the EC2 Transit Gateway propagation default route table. This cannot be configured or perform drift detection with Resource Access Manager shared EC2 Transit Gateways. Default value: true.
    
    Example:
    ```
    tgw_attachments = {
        security_vpc = {
            subnet_ids         = \<Subnet_id\>  
            vpc_id             = \<VPC_id\> 
        }
    }
    ```
    EOF
  type        = any
  default     = {}
  validation {
    condition = length(var.tgw_attachments) == 0 ? true : alltrue([
      for k, v in var.tgw_attachments : alltrue([
        for sk, sv in v : contains([
          "subnet_ids",
          "vpc_id",
          "appliance_mode_support",
          "dns_support",
          "ipv6_support",
          "transit_gateway_default_route_table_association",
          "transit_gateway_default_route_table_propagation"
        ], sk)
      ])
    ])
    error_message = "One or more argument(s) can not be identified, available options: subnet_ids, vpc_id, appliance_mode_support, dns_support, ipv6_support, transit_gateway_default_route_table_association, transit_gateway_default_route_table_propagation."
  }
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
    - general         :  Tags will add to all resources.
    - tgw             :  Tags for Transit gateway.
    - tgw_attachment  :  Tags for Transit gateway attachment.
    
  Example:
  ```
  tags = {
    general = {
      Created_from = "Terraform"
    },
    tgw = {
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
        "tgw",
        "tgw_attachment"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: general, tgw, tgw_attachment."
  }
}
