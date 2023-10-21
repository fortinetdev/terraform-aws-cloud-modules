## Route table
variable "existing_rt" {
  description = <<-EOF
    Using existing route table. 
    If the id is specified, will use this route table ID. Otherwise, will search the route table based on the given infomation.
    Options:
        - id         :  ID of the specific route table.
        - name       :  Name of the specific Vroute tablePC to retrieve.
        - tags       :  Map of tags, each pair of which must exactly match a pair on the desired route table.
        
    Example:
    ```
    existing_rt = {
        name = "default_route"
        tags = {
            \<Option\> = \<Option value\>
        }
    }
    ```
    EOF
  type        = any
  default     = null
  validation {
    condition = var.existing_rt == null ? true : alltrue([
      for k, v in var.existing_rt : contains([
        "id",
        "name",
        "tags"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: id, name, tags."
  }
}

variable "vpc_id" {
  description = "The VPC ID."
  type        = string
  default     = null
}

variable "rt_name" {
  description = "The route table name."
  type        = string
  default     = null
}

## Route
variable "routes" {
  description = <<-EOF
        Route entries configuration for the target route table.
        Format:
        ```
            routes = {
                \<Route entry name\> = {
                    \<Option\> = \<Option value\>
                }
            }
        ```
        Route entry options:
            One of the following destination arguments must be supplied:
                - destination_cidr_block      : (Optional|string) The destination CIDR block.
                - destination_ipv6_cidr_block : (Optional|string) The destination IPv6 CIDR block.
                - destination_prefix_list_id  : (Optional|string) The ID of a managed prefix list destination.
            One of the following target arguments must be supplied:
                - carrier_gateway_id          : (Optional|string) Identifier of a carrier gateway. This attribute can only be used when the VPC contains a subnet which is associated with a Wavelength Zone.
                - core_network_arn            : (Optional|string) The Amazon Resource Name (ARN) of a core network.
                - egress_only_gateway_id      : (Optional|string) Identifier of a VPC Egress Only Internet Gateway.
                - gateway_id                  : (Optional|string) Identifier of a VPC internet gateway or a virtual private gateway.
                - nat_gateway_id              : (Optional|string) Identifier of a VPC NAT gateway.
                - local_gateway_id            : (Optional|string) Identifier of a Outpost local gateway.
                - network_interface_id        : (Optional|string) Identifier of an EC2 network interface.
                - transit_gateway_id          : (Optional|string) Identifier of an EC2 Transit Gateway.
                - vpc_endpoint_id             : (Optional|string) Identifier of a VPC Endpoint.
                - vpc_peering_connection_id   : (Optional|string) Identifier of a VPC peering connection.
        Example:
        ```
        routes = {
            to_igw = {
                destination_cidr_block = "0.0.0.0/0"
                gateway_id = "igw-12345678"
            }
        }
        ```    
    EOF
  type        = map(map(string))
  default     = {}
  validation {
    condition = var.routes == null ? true : alltrue([
      for k, v in var.routes : alltrue([
        for sk, sv in v : contains([
          "destination_cidr_block",
          "destination_ipv6_cidr_block",
          "destination_prefix_list_id",
          "carrier_gateway_id",
          "core_network_arn",
          "egress_only_gateway_id",
          "gateway_id",
          "nat_gateway_id",
          "local_gateway_id",
          "network_interface_id",
          "transit_gateway_id",
          "vpc_endpoint_id",
          "vpc_peering_connection_id"
        ], sk)
      ])
    ])
    error_message = "One or more argument(s) can not be identified, available options: destination_cidr_block, destination_ipv6_cidr_block, destination_prefix_list_id, carrier_gateway_id, core_network_arn, egress_only_gateway_id, gateway_id, nat_gateway_id, local_gateway_id, network_interface_id, transit_gateway_id, vpc_endpoint_id, vpc_peering_connection_id."
  }
}

variable "rt_association_subnets" {
  description = "Subnet IDs to associate to current route table."
  type        = list(string)
  default     = []
}

variable "rt_association_gateways" {
  description = "Gateway IDs to associate to current route table."
  type        = list(string)
  default     = []
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
    - rt      :  Tags for route table.
    
  Example:
  ```
  tags = {
    general = {
      Created_from = "Terraform"
    },
    rt = {
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
        "rt"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: general, rt."
  }
}