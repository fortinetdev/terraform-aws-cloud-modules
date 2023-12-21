## VPC
variable "existing_vpc" {
  description = <<-EOF
    Using existing VPC. 
    If the id is specified, will use this VPC ID. Otherwise, will search the VPC based on the given infomation.
    Options:
        - cidr_block :  Cidr block of the desired VPC.
        - id         :  ID of the specific VPC.
        - name       :  Name of the specific VPC to retrieve.
        - tags       :  Map of tags, each pair of which must exactly match a pair on the desired VPC.
        
    Example:
    ```
    existing_vpc = {
        name = "Security_VPC"
        tags = {
            \<Option\> = \<Option value\>
        }
    }
    ```
    EOF
  type        = any
  default     = null
  validation {
    condition = var.existing_vpc == null ? true : alltrue([
      for k, v in var.existing_vpc : contains([
        "cidr_block",
        "id",
        "name",
        "tags"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: cidr_block, id, name, tags."
  }
}

variable "vpc_name" {
  description = "VPC name."
  type        = string
  default     = ""
}

variable "vpc_cidr_block" {
  description = "The IPv4 CIDR block for the VPC."
  type        = string
}

variable "enable_dns_support" {
  description = "A boolean flag to enable/disable DNS support in the VPC. Defaults to true."
  type        = bool
  default     = true
}

variable "enable_dns_hostnames" {
  description = "A boolean flag to enable/disable DNS hostnames in the VPC. Defaults false."
  type        = bool
  default     = false
}

variable "instance_tenancy" {
  description = <<-EOF
    A tenancy option for instances launched into the VPC. 
    Default is default, which ensures that EC2 instances launched in this VPC use the EC2 instance tenancy attribute specified when the EC2 instance is launched. 
    The only other option is dedicated, which ensures that EC2 instances launched in this VPC are run on dedicated tenancy instances regardless of the tenancy attribute specified at launch. 
    This has a dedicated per region fee of $2 per hour, plus an hourly per instance usage fee.
    EOF
  type        = string
  default     = "default"
}

variable "assign_generated_ipv6_cidr_block" {
  description = "Requests an Amazon-provided IPv6 CIDR block with a /56 prefix length for the VPC. You cannot specify the range of IP addresses, or the size of the CIDR block. Default is false."
  type        = bool
  default     = false
}

## IGW
variable "igw_name" {
  description = "Internet Gateway name. Default empty string, which means do not create IGW."
  type        = string
  default     = ""
}

variable "existing_igw" {
  description = <<-EOF
    Using existing IGW. 
    If the id is specified, will use this IGW ID. Otherwise, will search the IGW based on the given infomation.
    Options:
        - id         :  ID of the specific IGW.
        - name       :  Name of the specific IGW to retrieve.
        - tags       :  Map of tags, each pair of which must exactly match a pair on the desired IGW.
        
    Example:
    ```
    existing_igw = {
        name = "Security_IGW"
        tags = {
            \<Option\> = \<Option value\>
        }
    }
    ```
    EOF
  type        = any
  default     = null
  validation {
    condition = var.existing_igw == null ? true : alltrue([
      for k, v in var.existing_igw : contains([
        "id",
        "name",
        "tags"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: id, name, tags."
  }
}

## Security groups
variable "security_groups" {
  description = <<-EOF
        Security groups configuration for the target VPC.
        Format:
        ```
            security_groups = {
                \<Security group name\> = {
                    description = "\<Description\>"
                    ingress     = {
                        \<Rule name1\> = {
                            \<Option\> = \<Option value\>
                        }
                    }
                    egress     = {
                        \<Rule name1\> = {
                            \<Option\> = \<Option value\>
                        }
                    }
                }
            }
        ```
        Security groups options:
            - description  : (Optional|string) Security group description. Cannot be empty string(""), and also can not be updated after created. This field maps to the AWS `GroupDescription` attribute, for which there is no Update API. If you'd like to classify your security groups in a way that can be updated, use `tags`.
            - ingress      : (Optional|map) Configuration block for ingress rules.
            - egress       : (Optional|map) Configuration block for egress rules.

        Ingress options:
            - from_port         : (Required|string) Start port (or ICMP type number if protocol is icmp or icmpv6).
            - to_port           : (Required|string) End range port (or ICMP code if protocol is icmp).
            - protocol          : (Required|string) Protocol.
            - cidr_blocks       : (Optional|list)  List of CIDR blocks.
            - description       : (Optional|string) Description of this ingress rule.
            - ipv6_cidr_blocks  : (Optional|list) List of IPv6 CIDR blocks.
            - prefix_list_ids   : (Optional|list) List of Prefix List IDs.
            - security_groups   : (Optional|list) List of security groups. A group name can be used relative to the default VPC. Otherwise, group ID.
        
        Egress options:
            - from_port         : (Required|string) Start port (or ICMP type number if protocol is icmp).
            - to_port           : (Required|string) End range port (or ICMP code if protocol is icmp).
            - protocol          : (Required|string) Protocol.
            - cidr_blocks       : (Optional|list)  List of CIDR blocks.
            - description       : (Optional|string) Description of this egress rule.
            - ipv6_cidr_blocks  : (Optional|list) List of IPv6 CIDR blocks.
            - prefix_list_ids   : (Optional|list) List of Prefix List IDs.
            - security_groups   : (Optional|list) List of security groups. A group name can be used relative to the default VPC. Otherwise, group ID.
        
        Example:
        ```
        security_groups = {
            secgrp1 = {
                description = "Security group by Terraform"
                ingress     = {
                    https = {
                        from_port         = "443"
                        to_port           = "443"
                        protocol          = "tcp"
                        cidr_blocks       = [ "0.0.0.0/0" ]
                    }
                }
                egress     = {
                    all_traffic = {
                        from_port         = "0"
                        to_port           = "0"
                        protocol          = "tcp"
                        cidr_blocks       = [ "0.0.0.0/0" ]
                    }
                }
            }
        }
        ```
    EOF
  type        = any
  default     = {}
  validation {
    condition = var.security_groups == null ? true : alltrue([
      for k, v in var.security_groups : alltrue([
        for sk, sv in v : contains([
          "description",
          "ingress",
        "egress"], sk)
      ])
    ])
    error_message = "One or more argument(s) can not be identified, available options: description, ingress, egress."
  }
  validation {
    condition = var.security_groups == null ? true : alltrue([
      for k, v in var.security_groups :
      alltrue([
        for sk, sv in v : contains(["ingress", "egress"], sk) ? alltrue([
          for rk, rv in sv : alltrue([
            for srk, srv in rv : contains([
              "from_port",
              "to_port",
              "protocol",
              "cidr_blocks",
              "description",
              "ipv6_cidr_blocks",
              "prefix_list_ids",
              "security_groups"
            ], srk)
          ])
        ]) : true
      ])
    ])
    error_message = "One or more argument(s) on ingress or egress can not be identified, available options: from_port, to_port, protocol, cidr_blocks, description, ipv6_cidr_blocks, prefix_list_ids, security_groups."
  }
}

## Subnets
variable "subnets" {
  description = <<-EOF
        Subnets configuration for the target VPC.
        Format:
        ```
            subnets = {
                \<Subnet name\> = {
                    \<Option\> = \<Option value\>
                }
            }
        ```
        Subnet options:
            - cidr_block  : (Optional|string) The IPv4 CIDR block for the subnet.
            - availability_zone  : (Optional|string) AZ for the subnet.
            - map_public_ip_on_launch  : (Optional|string) Specify true to indicate that instances launched into the subnet should be assigned a public IP address. Default is false.
        Example:
        ```
        subnets = {
            fgt_asg = {
                cidr_block = "10.0.1.0/24"
                availability_zone = "us-west-2a"
            }
        }
        ```    
    EOF
  type        = any
  default     = {}
  validation {
    condition = var.subnets == null ? true : alltrue([
      for k, v in var.subnets : alltrue([
        for sk, sv in v : contains([
          "cidr_block",
          "availability_zone",
          "map_public_ip_on_launch"
        ], sk)
      ])
    ])
    error_message = "One or more argument(s) can not be identified, available options: cidr_block, availability_zone, map_public_ip_on_launch."
  }
}

## Tag related
variable "tags" {
  description = <<-EOF
  Tags that applies to related resources.
  Format:
  ```
    tags = {
        <Option> = <Option value>
    }
  ```
  Options:
    - general         :  Tags will add to all resources.
    - vpc             :  Tags for VPC.
    - igw             :  Tags for Internet gateway.
    - security_group  :  Tags for Security group.
    - subnet          :  Tags for Subnets.
    
  Example:
  ```
  tags = {
    general = {
      Created_from = "Terraform"
    },
    vpc = {
      Used_to = "ASG"
    }
  }
  ```
  EOF

  default = {}
  type    = map(map(string))
  validation {
    condition = length(var.tags) == 0 ? true : alltrue([
      for k, v in var.tags : contains([
        "general",
        "vpc",
        "igw",
        "security_group",
        "subnet"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: general, vpc, igw, security_group, subnet."
  }
}
