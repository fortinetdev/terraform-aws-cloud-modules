## Root config
variable "access_key" {
  description = "The Access Key of AWS account."
  type        = string
  default     = ""
}

variable "secret_key" {
  description = "The Secret Key of AWS account."
  type        = string
  default     = ""
}

variable "region" {
  description = "The region to deploy the VPC."
  type        = string
}

## Tag
variable "general_tags" {
  description = "The tags that will apply to all resouces."
  type        = map(string)
  default     = {}
}

## VPC
variable "vpc_name" {
  description = "VPC name for the security VPC."
  type        = string
  default     = "security-vpc"
}

variable "igw_name" {
  description = "Internet Gateway name for the security VPC."
  type        = string
  default     = "security-vpc-igw"
}

variable "existing_security_vpc" {
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
    existing_security_vpc = {
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
    condition = var.existing_security_vpc == null ? true : alltrue([
      for k, v in var.existing_security_vpc : contains([
        "cidr_block",
        "id",
        "name",
        "tags"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: cidr_block, id, name, tags."
  }
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

variable "existing_security_groups" {
  description = "Existing Security group names."
  type        = list(string)
  default     = []
}

variable "vpc_cidr_block" {
  description = "The IPv4 CIDR block for the VPC."
  type        = string
  default     = ""
}

variable "subnets" {
  description = <<-EOF
        Subnets configuration for the target VPC.
        The format of subnet name should be follow the name prefix of \"fgt_login_\", \"fgt_internal_\", \"tgw_attachment_\", \"gwlbe_\", \"privatelink_\". Specify the target subnet you needed.
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
            fgt_mgmt = {
                cidr_block = "10.0.1.0/24"
                availability_zone = "us-west-2a"
            }
        }
        ```    
    EOF
  type        = any
  default     = null
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

variable "existing_subnets" {
  description = <<-EOF
    Using existing subnets. 
    Name format should be follow the name prefix of \"fgt_login_\", \"fgt_internal_\", \"tgw_attachment_\", \"gwlbe_\", \"privatelink_\".
    Options:
        - id                      :  (Required|string) Subnet ID.
        - availability_zone       :  (Required|string) AZ for the subnet.
        
    Example:
    ```
    existing_subnets = {
      "fgt_login_us-east-2a" = {
        id                = "subnet-123456789"
        availability_zone = "us-east-2a"
      }
    }
    ```
    EOF
  type        = any
  default     = null
  validation {
    condition = var.existing_subnets == null ? true : alltrue([
      for k, v in var.existing_subnets : alltrue([
        for sk, sv in v : contains([
          "id",
          "availability_zone"
        ], sk)
      ])
    ])
    error_message = "One or more argument(s) can not be identified, available options: id, availability_zone."
  }
}

variable "route_tables" {
  description = <<-EOF
    Dictionary of Route tables. 
    Key is the route table name.
    Options:
        - rt_association_subnets  :  (Optional|list) List of map for subnets to associate to current route table.
          Options:
          - id : (Optional|string) ID of the subnet.
          - name : (Optional|string) Name of the subnet that created by this example.
        - rt_association_gateways :  (Optional|list) List of map for gateways to associate to current route table.
          Options:
          - id : (Optional|string) ID of the Gateway.
          - name : (Optional|string) Name of the Gateway that created by this example.
        - routes                  :  (Optional|map) Gateway IDs to associate to current route table.
          Options:
          One of the following destination arguments must be supplied:
              - destination_cidr_block      : (Optional|string) The destination CIDR block.
              - destination_ipv6_cidr_block : (Optional|string) The destination IPv6 CIDR block.
              - destination_prefix_list_id  : (Optional|string) The ID of a managed prefix list destination.
          One of the following target arguments must be supplied:
              - carrier_gateway_id          : (Optional|string) Identifier of a carrier gateway. This attribute can only be used when the VPC contains a subnet which is associated with a Wavelength Zone.
              - core_network_arn            : (Optional|string) The Amazon Resource Name (ARN) of a core network.
              - egress_only_gateway_id      : (Optional|string) Identifier of a VPC Egress Only Internet Gateway.
              - gateway                  : (Optional|string) Identifier of a VPC internet gateway or a virtual private gateway.
                Options:
                - id : (Optional|string) ID of the Gateway.
                - name : (Optional|string) Name of the Gateway that created by this example.
              - nat_gateway              : (Optional|string) Identifier of a VPC NAT gateway.
                Options:
                - id : (Optional|string) ID of the NAT Gateway.
              - local_gateway_id            : (Optional|string) Identifier of a Outpost local gateway.
              - network_interface        : (Optional|string) Identifier of an EC2 network interface.
                Options:
                - id : (Optional|string) ID of the network interface.
                - name : (Optional|string) Format "<fgt_name>.<interface_name>", FortiGate name and network interface name are from variable `fgts`.
              - transit_gateway_id          : (Optional|string) Identifier of an EC2 Transit Gateway.
              - vpc_endpoint_id             : (Optional|string) Identifier of a VPC Endpoint.
              - vpc_peering_connection_id   : (Optional|string) Identifier of a VPC peering connection.
    Example:
    ```
    route_tables = {
      fgt_login = {
        routes = {
          to_igw = {
            destination_cidr_block   = "0.0.0.0/0"
            gateway = {
              name = "security-vpc-igw"
            }
          }
        }
        rt_association_subnets = [
          {
            name = "fgt_mgmt"
          }
        ]
      }
    }
    ```
    EOF
  type = map(
    object({
      rt_association_subnets = optional(list(object({
        id   = optional(string, null)
        name = optional(string, null)
      })), [])
      rt_association_gateways = optional(list(object({
        id   = optional(string, null)
        name = optional(string, null)
      })), [])
      routes = optional(map(object({
        destination_cidr_block      = optional(string, null)
        destination_ipv6_cidr_block = optional(string, null)
        destination_prefix_list_id  = optional(string, null)
        carrier_gateway_id          = optional(string, null)
        core_network_arn            = optional(string, null)
        egress_only_gateway_id      = optional(string, null)
        gateway = optional(object({
          id   = optional(string, null)
          name = optional(string, null)
        }), null)
        nat_gateway = optional(object({
          id = optional(string, null)
        }), null)
        local_gateway_id = optional(string, null)
        network_interface = optional(object({
          id   = optional(string, null)
          name = optional(string, null)
        }), null)
        transit_gateway_id        = optional(string, null)
        vpc_endpoint_id           = optional(string, null)
        vpc_peering_connection_id = optional(string, null)
      })), null)
    })
  )
  default = {}
}

## FortiGate configuration
variable "fgts" {
  description = <<-EOF
  FortiGate instance map.
  Format:
  ```
    fgts = {
        \<FORTIGATE NAME\> = {
            \<Option\> = \<Option value\>
        }
    }
  ```
  Options:
    FortiGate instance template
    - ami_id : (Optional|string) The AMI ID of FortiOS image. If you leave this blank, Terraform will get the AMI ID from AWS market place with the given FortiOS version.
    - fgt_version : (Optional|string) FortiGate version for the FortiGate instances. If the whole version been provided, please make sure the version is exist. If part of version been provided, such as 7.2, will using the latest release of this version.
    - instance_type : (Optional|string) Instance type for the FortiGate instances. Default is c5.xlarge.
    - license_type : (Optional|string) License type for the FortiGate instances. Options: on_demand, byol. Default is on_demand.
    - fgt_hostname : (Optional|string) FortiGate instance hostname.
    - fgt_password : (Optional|string) FortiGate instance login password. This is required for BYOL type of FortiGate instance since we need to upload the license to the instance by lambda function.
    - fgt_multi_vdom : (Optional|bool) Flag of FortiGate instance vdom type. `true` will be multi-vdom mode. `false` will be single-vdom mode. Default is `false`.
    - lic_file_path : (Optional|string) File path of FortiGate license file.
    - fortiflex_token : (Optional|string) FortiFlex token that used to activate FortiGate instance.
    - keypair_name : (Required|string) The keypair name for accessing the FortiGate instances.
    - fgt_admin_https_port : (Optional|string) FortiGate instance HTTPS admin access port.
    - fgt_admin_ssh_port : (Optional|string) FortiGate instance SSH admin access port.
    - user_conf_content: (Optional|string) User configuration in CLI format that will applied to the FortiGate instance.
    - user_conf_file_path : (Optional|string) User configuration file path that will applied to FortiGate instance.
    - cpu_options : (Optional|map) CPU options apply to the instance at launch time.
      Options:
      - amd_sev_snp : (Optional|string) Indicates whether to enable the instance for AMD SEV-SNP. AMD SEV-SNP is supported with M6a, R6a, and C6a instance types only. Valid values are enabled and disabled.
      - core_count : (Optional|int) Sets the number of CPU cores for an instance.
      - threads_per_core : (Optional|int) If set to 1, hyperthreading is disabled on the launched instance. Defaults to 2 if not set.
    - network_interfaces : (Optional|map) Network interfaces configuration for FortiGate VM instance.
      Options:
      - device_index       : (Required|int) Integer to define the network interface index. Interface with `0` will be attached at boot time.
      - vdom               : (Optional|string) Vdom name that the interface belongs to. Only works when vdom mode is multi-vdom. Default will be root if not set and vdom mode is multi-vdom.
      - description        : (Optional|string) Description for the network interface.
      - private_ips        : (Optional|list) List of private IPs to assign to the ENI without regard to order.
      - source_dest_check  : (Optional|bool) Whether to enable source destination checking for the ENI. Defaults false.
      - enable_public_ip   : (Optional|bool) Whether to assign a public IP for the ENI. Defaults to false.
      - public_ipv4_pool   : (Optional|string) Specify EC2 IPv4 address pool. If not set, Amazon's poll will be used. Only useful when `enable_public_ip` is set to true.
      - existing_eip_id    : (Optional|string) Associate an existing EIP to the ENI. Sould set enable_public_ip to false.
      - subnet          : (Required|map) Subnet infomation to create the interface.
        Options:
        - id : (Optional|string) ID of the Subnet.
        - name : (Optional|string) Name of the Subnet that managed by this example.
      - security_groups    : (Optional|list) List of map of security group to assign to the ENI. Defaults null.
        Options:
        - id : (Optional|string) ID of the Gateway.
        - name : (Optional|string) Name of the Gateway that created by this example.
  
  Example:
  ```
  fgts = {
    fgt_byol = {
      fgt_version = "7.2"
      license_type = "byol"
      fgt_password = "ftnt"
      keypair_name = "keypair1"
      network_interfaces = {
        mgmt = {
          device_index       = 0
          subnet_id          = {
            name = "fgt_mgmt"
          }
          enable_public_ip   = true
          source_dest_check  = true
          security_groups = [{
            id = "\<SECURITY_GROUP_ID\>"
          }]
        },
        port2 = {
          device_index     = 1
          subnet_id        = {
            id = \<SUBNET_ID\>
          }
          existing_eip_id  = \<ELISTIC_IP_ID\>
        }
      }
    }
  }
  ```
  EOF
  type = map(object({
    ami_id               = optional(string, "")
    fgt_version          = optional(string, "")
    instance_type        = optional(string, "c5n.xlarge")
    license_type         = optional(string, "on_demand")
    fgt_hostname         = optional(string, "")
    fgt_password         = optional(string, "")
    fgt_multi_vdom       = optional(string, false)
    lic_file_path        = optional(string, "")
    fortiflex_token      = optional(string, "")
    keypair_name         = string
    fgt_admin_https_port = optional(string, "")
    fgt_admin_ssh_port   = optional(string, "")
    user_conf_content    = optional(string, "")
    user_conf_file_path  = optional(string, "")
    network_interfaces = optional(map(object({
      device_index      = number
      vdom              = optional(string)
      description       = optional(string)
      private_ips       = optional(list(string))
      source_dest_check = optional(bool)
      enable_public_ip  = optional(bool)
      public_ipv4_pool  = optional(string)
      existing_eip_id   = optional(string)
      subnet = optional(object({
        id   = optional(string)
        name = optional(string)
      }))
      security_groups = optional(list(object({
        id   = optional(string)
        name = optional(string)
      })))
    })), {})

  }))
  default = {}
}

# General
variable "module_prefix" {
  description = "Prefix that will be used in the whole module."
  type        = string
  default     = ""
}
