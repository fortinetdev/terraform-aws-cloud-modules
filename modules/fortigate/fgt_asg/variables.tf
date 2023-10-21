## FortiGate instance template
variable "template_name" {
  description = "The name of the launch template. If you leave this blank, Terraform will auto-generate a unique name."
  type        = string
  default     = ""
}
variable "keypire_name" {
  description = "The keypair name that used in FortiGate EC2 instance."
  type        = string
}

variable "availability_zones" {
  description = "List of one or more availability zones for the group. "
  type        = list(string)
  default     = []
}

variable "az_name_map" {
  description = "Name map for availability. "
  type        = map(string)
  default     = {}
}

variable "instance_type" {
  description = "Provide the instance type for the FortiGate instances"
  default     = "c5.xlarge"
  type        = string
}

variable "license_type" {
  description = "Provide the license type for the FortiGate instances. Options: on_demand, byol. Default is on_demand."
  default     = "on_demand"
  type        = string
}

variable "fgt_hostname" {
  description = "FortiGate instance hostname."
  default     = ""
  type        = string
}

variable "fgt_password" {
  description = "FortiGate instance login password. This is required for BYOL type of FortiGate instance since we need to upload the license to the instance by lambda function."
  type        = string
}

variable "fgt_multi_vdom" {
  description = "Whether FortiGate instance enable multi-vdom mode. Default is false. Note: Only license_type set to byol could enable multi-vdom mode."
  default     = false
  type        = bool
}

variable "fgt_version" {
  description = "Provide the FortiGate version for the FortiGate instances. If the whole version been provided, please make sure the version is exist. If part of version been provided, such as 7.2, will using the latest release of this version. Default is 7.2."
  default     = "7.2"
  type        = string
}

variable "user_conf" {
  description = "User configuration in CLI format that will applied to the FortiGate instance."
  default     = ""
  type        = string
}

variable "user_conf_s3" {
  description = <<-EOF
  User configuration files in AWS S3 that will applied to FortiGate instance.
  The key is the Bucket name, and the value is a list of key names in this Bucket.
  Format:
  ```
    user_conf_s3 = {
        \<Bucket name\> = []
    }
  ```
  EOF
  default     = {}
  type        = map(list(string))
}

variable "network_interfaces" {
  description = <<-EOF
  Network interfaces configuration for FortiGate VM instance.
  Format:
  ```
    network_interfaces = {
        \<Key\> = {
            \<Option\> = \<Option value\>
        }
    }
  ```
  Key:
    Name of the interface.
  Options:
    - device_index       : (Required|int) Integer to define the network interface index. Interface with `0` will be attached at boot time.
    - subnet_id_map      : (Required|map) Subnet ID map to create the ENI in. The key is the Availability Zone name of the subnet, and the value is the Subnet ID.
    - vdom               : (Optional|string) Vdom name that the interface belongs to. Only works when vdom mode is multi-vdom. Default will be root if not set and vdom mode is multi-vdom.
    - description        : (Optional|string) Description for the network interface.
    - to_gwlb            : (Optional|bool) If set to true, that means this port is connected to the Gateway Load Balancer.
    - private_ips        : (Optional|list) List of private IPs to assign to the ENI without regard to order.
    - source_dest_check  : (Optional|bool) Whether to enable source destination checking for the ENI. Defaults false.
    - security_groups    : (Optional|list) List of security group IDs to assign to the ENI. Defaults null.
    - enable_public_ip   : (Optional|bool) Whether to assign a public IP for the ENI. Defaults to false.
    - public_ipv4_pool   : (Optional|string) Specify EC2 IPv4 address pool. If not set, Amazon's poll will be used. Only useful when `enable_public_ip` is set to true.
    - existing_eip_id    : (Optional|string) Associate an existing EIP to the ENI. Sould set enable_public_ip to false.
  
  Example:
  ```
  network_interfaces = {
    mgmt = {
      device_index       = 1
      subnet_id_map          = {
        \<AZ_NAME\> = \<SUBNET_ID\>
      }
      enable_public_ip   = true
      source_dest_check  = true
      security_groups = ["\<SECURITY_GROUP_ID\>"]
    },
    public1 = {
      device_index     = 0
      subnet_id_map        = {
        \<AZ_NAME\> = \<SUBNET_ID\>
      }
      existing_eip_id  = \<ELISTIC_IP_ID\>
    }
  }
  ```
  EOF

  type = any
  validation {
    condition = var.network_interfaces == null ? true : alltrue([
      for k, v in var.network_interfaces :
      alltrue([
        for sk, sv in v : contains([
          "device_index",
          "subnet_id_map",
          "vdom",
          "description",
          "to_gwlb",
          "private_ips",
          "source_dest_check",
          "security_groups",
          "enable_public_ip",
          "public_ipv4_pool",
        "existing_eip_id"], sk)
      ])
    ])
    error_message = "One or more argument(s) can not be identified, available options: device_index, subnet_id_map, vdom, description, to_gwlb, private_ips, source_dest_check, security_groups, enable_public_ip, public_ipv4_pool, existing_eip_id."
  }
  validation {
    condition = var.network_interfaces == null ? true : alltrue([
      for k, v in var.network_interfaces : contains(keys(v), "device_index") && contains(keys(v), "subnet_id_map")
    ])
    error_message = "Arguments device_index and subnet_id_map are required."
  }
}

## FGT config
variable "gwlb_ips" {
  description = <<-EOF
  Gateway Load Balancer IPs that used for FortiGate configuration.
  Format:
  ```
    gwlb_ips = {
          \<Subnet_id\> = \<IP\>
    }
  ```
  Example:
  ```
  gwlb_ips = {
    subnet-12345678 = 10.0.0.47
  }
  ```
  EOF
  type        = map(string)
  default     = {}
}

variable "create_geneve_for_all_az" {
  description = "If true, FotiGate instance will create GENEVE turnnels for all availability zones. Set to true if Gateway Load Balancer enabled cross zone load balancing."
  type        = bool
  default     = false
}

variable "enable_fgt_system_autoscale" {
  description = "If true, FotiGate system auto-scale will be set."
  type        = bool
  default     = false
}

variable "fgt_system_autoscale_psksecret" {
  description = "FotiGate system auto-scale psksecret."
  type        = string
  default     = ""
}

variable "fgt_login_port_number" {
  description = "The port number for the FortiGate instance. Should set this parameter if the port number for FortiGate instance login is not 443."
  type        = string
  default     = ""
}

## Auto Scaling Group
variable "asg_name" {
  description = "Name of the Auto Scaling Group."
  type        = string
}

variable "asg_max_size" {
  description = "Maximum size of the Auto Scaling Group."
  type        = number
}

variable "asg_min_size" {
  description = "Minimum size of the Auto Scaling Group."
  type        = number
}

variable "asg_desired_capacity" {
  description = "Number of Amazon EC2 instances that should be running in the group."
  type        = number
  default     = null
}

variable "asg_health_check_grace_period" {
  description = "Time (in seconds) after instance comes into service before checking health."
  type        = number
  default     = 300
}

variable "asg_health_check_type" {
  description = "'EC2' or 'ELB'. Controls how health checking is done."
  type        = string
  default     = ""
}

variable "asg_gwlb_tgp" {
  description = "Set of aws_alb_target_group ARNs"
  type        = list(string)
  default     = []
}

variable "create_dynamodb_table" {
  description = "If true, will create the DynamoDB table using dynamodb_table_name as the name. Default is false."
  type        = bool
  default     = false
}

variable "dynamodb_table_name" {
  description = "DynamoDB table name that used for tracking Auto Scale Group information, such as instance information and primary IP."
  type        = string
}

variable "scale_policies" {
  description = <<-EOF
  Auto Scaling group scale policies.
  Format:
  ```
    scale_policies = {
        \<Policy name\> = {
            \<Option\> = \<Option value\>
        }
    }
  ```
  Options:
    - policy_type               : (Required|string) Policy type, either "SimpleScaling", "StepScaling", "TargetTrackingScaling", or "PredictiveScaling".
    - adjustment_type           : (Optional|string) Whether the adjustment is an absolute number or a percentage of the current capacity. Valid values are ChangeInCapacity, ExactCapacity, and PercentChangeInCapacity.
    Options only for SimpleScaling:
    - cooldown           : (Optional|number) Amount of time, in seconds, after a scaling activity completes and before the next scaling activity can start.
    - scaling_adjustment : (Optional|string) Number of instances by which to scale. adjustment_type determines the interpretation of this number (e.g., as an absolute number or as a percentage of the existing Auto Scaling group size). A positive increment adds to the current capacity and a negative value removes from the current capacity.
    Options only for TargetTrackingScaling:
    - target_tracking_configuration : (Optional|map) Target tracking policy.
      Options for parameter target_tracking_configuration:
      - target_value                    : (Required|number) Target value for the metric.
      - disable_scale_in                : (Optional|bool) Whether scale in by the target tracking policy is disabled. Default: false.
      - estimated_instance_warmup : (Optional|number) Estimated time, in seconds, until a newly launched instance will contribute CloudWatch metrics.
      - predefined_metric_specification : (Optional|map) Predefined metric.
        Options for parameter predefined_metric_specification:
        - predefined_metric_type : (Required|string) Metric type.
        - resource_label         : (Optional|string) Identifies the resource associated with the metric type.
  
  Example:
  ```
  scale_policies = {
      cpu_above_80 = {
          policy_type               = "TargetTrackingScaling"
          estimated_instance_warmup = 60
          target_tracking_configuration = {
            target_value = 80
            predefined_metric_specification = {
              predefined_metric_type = "ASGAverageCPUUtilization"
            }
          }
      }
  }
  ```
  EOF

  type    = any
  default = {}
}

## Lambda
variable "lambda_timeout" {
  description = "Amount of time your Lambda Function has to run in seconds. Defaults to 300."
  type        = number
  default     = 300
}

variable "lic_s3_name" {
  description = "AWS S3 bucket name that contains FortiGate license files or token json file."
  type        = string
  default     = null
}

variable "lic_folder_path" {
  description = "Folder path of FortiGate license files or token json file."
  type        = string
  default     = null
}

variable "fortiflex_refresh_token" {
  description = "Refresh token used for FortiFlex."
  type        = string
  default     = null
}

variable "fortiflex_sn_list" {
  description = "Serial number list from FortiFlex account that used to activate FortiGate instance."
  type        = list(any)
  default     = []
}

variable "fortiflex_configid_list" {
  description = "Config ID list from FortiFlex account that used to activate FortiGate instance."
  type        = list(any)
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
    - general     :  Tags will add to all resources.
    - template    :  Tags for launch template.
    - instance    :  Tags for FortiGate instance.
    - asg         :  Tags for Auto Scaling Group.
    - lambda      :  Tags for Lambda function.
    - iam         :  Tags for IAM related resources.
    - dynamodb    :  Tags for DynamoDB related resources.
    - s3          :  Tags for S3 related resources.
    - cloudwatch  :  Tags for CloudWatch related resources.
    
  Example:
  ```
  tags = {
    general = {
      Created_from = "Terraform"
    },
    template = {
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
        "template",
        "instance",
        "asg",
        "lambda",
        "iam",
        "dynamodb",
        "s3",
        "cloudwatch"
      ], k)
    ])
    error_message = "One or more argument(s) can not be identified, available options: general, template, asg, instance, lambda, iam, dynamodb, s3, cloudwatch."
  }
}