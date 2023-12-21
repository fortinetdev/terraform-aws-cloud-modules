## Existing resource
variable "existing_gwlb" {
  description = <<-EOF
    Using existing Gateway Load Balancer. 
    Options:
        - arn  :  (Optional|string) Full ARN of the load balancer.
        - name :  (Optional|string) Unique name of the load balancer.   
        - tags :  (Optional|map) Mapping of tags, each pair of which must exactly match a pair on the desired load balancer.
    Example:
    ```
    existing_gwlb = {
        name = "gwlb-fgt"
    }
    ```
    EOF
  type        = any
  default     = null
  validation {
    condition = var.existing_gwlb == null ? true : alltrue([
      for k, v in var.existing_gwlb : contains([
        "arn",
        "name",
        "tags"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: arn, name, tags."
  }
}

variable "existing_gwlb_tgp" {
  description = <<-EOF
    Using existing Gateway Load Balancer. 
    Options:
        - arn  :  (Optional|string) Full ARN of the target group.
        - name :  (Optional|string) Unique name of the target group.   
        - tags :  (Optional|map) Mapping of tags, each pair of which must exactly match a pair on the desired target group.
    Example:
    ```
    existing_gwlb_tgp = {
        name = "gwlb-tgp-fgt"
    }
    ```
    EOF
  type        = any
  default     = null
  validation {
    condition = var.existing_gwlb_tgp == null ? true : alltrue([
      for k, v in var.existing_gwlb_tgp : contains([
        "arn",
        "name",
        "tags"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: arn, name, tags."
  }
}

variable "existing_gwlb_ep_service" {
  description = <<-EOF
    Using existing Gateway Load Balancer VPC Endpoint Service. 
    Options:
        - service_name  :  (Optional|string) Service name that is specified when creating a VPC endpoint.
        - filter        :  (Optional|map) Configuration block(s) for filtering.   
        - tags          :  (Optional|map) Map of tags, each pair of which must exactly match a pair on the desired VPC Endpoint Service.
    Example:
    ```
    existing_gwlb_ep_service = {
        service_name = "gwlb-tgp-fgt"
    }
    ```
    EOF
  type        = any
  default     = null
  validation {
    condition = var.existing_gwlb_ep_service == null ? true : alltrue([
      for k, v in var.existing_gwlb_ep_service : contains([
        "service_name",
        "filter",
        "tags"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: service_name, filter, tags."
  }
}

## Gateway Load Balancer
variable "gwlb_name" {
  description = "Gateway Load Balancer name"
  default     = ""
  type        = string
}

variable "subnets" {
  description = <<-EOF
        Subnets list for the target Gateway Load Balancer.
        Example:
        ```
        subnets = ["subnet-12345678"]
        ```    
    EOF
  type        = list(string)
  default     = null
}

variable "enable_cross_zone_load_balancing" {
  description = "If true, cross-zone load balancing of the load balancer will be enabled."
  type        = bool
  default     = null
}

## Target Group
variable "tgp_name" {
  description = "Target Group name"
  default     = ""
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for the target group"
  default     = ""
  type        = string
}

variable "target_type" {
  description = "Target type of the target group. Available options: instance, ip, alb, lambda. Default is instance."
  default     = "instance"
  type        = string
}

variable "deregistration_delay" {
  description = "Amount time for Elastic Load Balancing to wait before changing the state of a deregistering target from draining to unused. The range is 0-3600 seconds. The default value is 300 seconds."
  default     = null
  type        = number
}

variable "health_check" {
  description = <<-EOF
        Health Check configuration block.
        Format:
        ```
        health_check = {
            \<Option\> = \<Option value\>
        }
        ```
        Options:
            - enabled              : (Optional|bool) Whether health checks are enabled. Defaults to true.
            - healthy_threshold    : (Optional|number) Number of consecutive health check successes required before considering a target healthy. The range is 2-10. Defaults to 3.
            - interval             : (Optional|number) Approximate amount of time, in seconds, between health checks of an individual target. The range is 5-300. For lambda target groups, it needs to be greater than the timeout of the underlying lambda. Defaults to 30.
            - path                 : (Optional|string) Destination for the health check request. Required for HTTP/HTTPS ALB and HTTP NLB. Only applies to HTTP/HTTPS.
            - port                 : (Optional|number) The port the load balancer uses when performing health checks on targets. Default is traffic-port.
            - protocol             : (Optional|string) Protocol the load balancer uses when performing health checks on targets. Must be either TCP, HTTP, or HTTPS. The TCP protocol is not supported for health checks if the protocol of the target group is HTTP or HTTPS. Defaults to HTTP.
            - timeout              : (Optional|number) Amount of time, in seconds, during which no response from a target means a failed health check. The range is 2-120 seconds. For target groups with a protocol of GENEVE, the default is 5 seconds.
            - unhealthy_threshold  : (Optional|number) Number of consecutive health check failures required before considering a target unhealthy. The range is 2-10. Defaults to 3.

        Example:
        ```
        health_check = {
            enabled              = true
            healthy_threshold    = 3
            interval             = 30
            port                 = 80
            protocol             = "TCP"
            timeout              = 5
            unhealthy_threshold  = 3
        }
        ```
    EOF
  default     = {}
  type        = any
  validation {
    condition = length(var.health_check) == 0 ? true : alltrue([
      for k, v in var.health_check : contains([
        "healthy_threshold",
        "interval",
        "path",
        "port",
        "protocol",
        "timeout",
        "unhealthy_threshold",
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: healthy_threshold, interval, path, port, protocol, timeout, unhealthy_threshold."
  }
}

## Target Group attachment
variable "gwlb_tg_attachments" {
  description = <<-EOF
        Gateway Load Balancer Target Group attachments configuration.
        Format:
        ```
        gwlb_tg_attachments = {
          "\<Attachment_name\>" = {
            \<Option\> = \<Option value\>
          }
        }
        ```
        Options:
            - tgp_target_id                : (Optional|string) The ID of the target. This is the Instance ID for an instance, or the container ID for an ECS container. If the target type is ip, specify an IP address. If the target type is lambda, specify the arn of lambda. If the target type is alb, specify the arn of alb.
            - tgp_attach_port              : (Optional|string) The port on which targets receive traffic.
            - tgp_attach_availability_zone : (Optional|string) The Availability Zone where the IP address of the target is to be registered. If the private ip address is outside of the VPC scope, this value must be set to 'all'.

        Example:
        ```
        gwlb_tg_attachments = {
          "fgt_instance1" = {
            tgp_target_id = i-01563a5f67d4e6010
          }
        }
        ```
    EOF
  default     = {}
  type        = map(map(string))
  validation {
    condition = length(var.gwlb_tg_attachments) == 0 ? true : alltrue([
      for k, v in var.gwlb_tg_attachments : alltrue([
        for sk, sv in v : contains([
          "tgp_target_id",
          "tgp_attach_port",
          "tgp_attach_availability_zone"
        ], sk)
      ])
    ])
    error_message = "One or more argument(s) can not be identified, available options: tgp_target_id, tgp_attach_port, tgp_attach_availability_zone."
  }
}

## Gateway Load balancer Listener
variable "gwlb_ln_name" {
  description = "Gateway Load Balancer Listener name."
  default     = null
  type        = string
}

## Gateway Load Balancer Endpoint
variable "gwlb_ep_service_name" {
  description = "Gateway Load Balancer Endpoint Service name."
  default     = ""
  type        = string
}

variable "gwlb_endps" {
  description = <<-EOF
    Gateway Load Balancer Endpoint map. 
    Format:
    ```
        gwlb_endps = {
            \<Endpoint name\> = {
                vpc_id         = \<VPC_id\>  
                subnet_id = \<Subnet_id\>
            }
        }
    ```
    Options:
        - vpc_id    : (Required|string) Identifier of EC2 VPC.
        - subnet_id : (Required|string) Identifiers of EC2 Subnet.
   
    Example:
    ```
    gwlb_endps = {
        gwlbe-secvpc-us-west-1b = {
            vpc_id    = "vpc-12345678"
            subnet_id = "subnet-123456789"
        }
    }
    ```
    EOF
  type        = map(map(string))
  default     = {}
  validation {
    condition = length(var.gwlb_endps) == 0 ? true : alltrue([
      for k, v in var.gwlb_endps : alltrue([
        for sk, sv in v : contains([
          "subnet_id",
          "vpc_id"
        ], sk)
      ])
    ])
    error_message = "One or more argument(s) can not be identified, available options: subnet_id, vpc_id."
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
    - gwlb            :  Tags for Gateway Load Balancer.
    - tgp             :  Tags for Target Group.
    - gwlb_ep_service :  Tags for Gateway Load Balancer Endpoint Service.
    - gwlb_endp       :  Tags for Gateway Load Balancer Endpoints.
    
  Example:
  ```
  tags = {
    general = {
      Created_from = "Terraform"
    },
    gwlb = {
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
        "gwlb",
        "tgp",
        "gwlb_ln",
        "gwlb_ep_service",
        "gwlb_endp"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: general, gwlb, tgp, gwlb_ln, gwlb_ep_service, gwlb_endp."
  }
}