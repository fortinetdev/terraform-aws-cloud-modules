## TGW Route table
variable "existing_tgw_rt" {
  description = <<-EOF
    Using existing Transit Gateway route table. 
    If the id is specified, will use this Transit Gateway route table ID. Otherwise, will search the route table based on the given infomation.
    Options:
        - id     :  ID of the specific route table.
        - filter :  One or more configuration blocks containing name-values filters. Note: the value should be a list.
        
    Example:
    ```
    existing_tgw_rt = {
        filter = {
            Name = [ "default_route" ]
        }
    }
    ```
    EOF
  type        = any
  default     = null
  validation {
    condition = var.existing_tgw_rt == null ? true : alltrue([
      for k, v in var.existing_tgw_rt : contains([
        "id",
        "filter"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: id, filter."
  }
}

variable "tgw_id" {
  description = "The Transit Gateway ID."
  type        = string
  default     = null
}

variable "tgw_rt_name" {
  description = "The Transit Gateway route table name."
  type        = string
  default     = null
}

## Route
variable "tgw_routes" {
  description = <<-EOF
        Route entries configuration for the target Transit Gateway route table.
        Format:
        ```
            tgw_routes = {
                \<Route entry name\> = {
                    \<Option\> = \<Option value\>
                }
            }
        ```
        Route entry options:
            - destination_cidr_block        : (Required|string) IPv4 or IPv6 RFC1924 CIDR used for destination matches. Routing decisions are based on the most specific match.
            - transit_gateway_attachment_id : (Optional|string) Identifier of EC2 Transit Gateway Attachment (required if blackhole is set to false).
            - blackhole                     : (Optional|bool) Indicates whether to drop traffic that matches this route (default to false).
        Example:
        ```
        tgw_routes = {
            to_secvpc = {
                destination_cidr_block = "0.0.0.0/0"
                transit_gateway_attachment_id = "tgw-attach-12345678"
            }
        }
        ```    
    EOF
  type        = map(map(string))
  default     = {}
  validation {
    condition = var.tgw_routes == null ? true : alltrue([
      for k, v in var.tgw_routes : alltrue([
        for sk, sv in v : contains([
          "destination_cidr_block",
          "transit_gateway_attachment_id",
          "blackhole"
        ], sk)
      ])
    ])
    error_message = "One or more argument(s) can not be identified, available options: destination_cidr_block, transit_gateway_attachment_id, blackhole."
  }
}

variable "tgw_rt_associations" {
  description = "Associations to current Transit Gateway route table."
  type        = list(string)
  default     = []
}

variable "tgw_rt_propagations" {
  description = "Propagations to current Transit Gateway route table."
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
    - tgw_rt      :  Tags for route table.
    
  Example:
  ```
  tags = {
    general = {
      Created_from = "Terraform"
    },
    tgw_rt = {
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
        "tgw_rt"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: general, tgw_rt."
  }
}