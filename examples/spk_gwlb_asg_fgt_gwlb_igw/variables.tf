## Root config
variable "access_key" {
  description = "The Access Key of AWS account."
  type        = string
}

variable "secret_key" {
  description = "The Secret Key of AWS account."
  type        = string
}

variable "region" {
  description = "The region to deploy the VPC."
  type        = string
}

## Tag
variable "general_tags" {
  description = "The tags that will apply to all resouces."
  type        = map(string)
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

variable "availability_zones" {
  description = "Availability Zones"
  type        = list(string)
}

variable "spoke_cidr_list" {
  description = "The IPv4 CIDR block list for the spoke VPCs."
  type        = list(string)
}

variable "vpc_cidr_block" {
  description = "The IPv4 CIDR block for the VPC."
  type        = string
  validation {
    condition     = tonumber(element(split("/", var.vpc_cidr_block), 1)) <= 24
    error_message = <<-EOF
    Auto set subnet do not support netmask larger then 24. Current netmask is "${tonumber(element(split("/", var.vpc_cidr_block), 1))}". Please provide a CIDR block with netmask smaler or equal to 24. Otherwise, please delete this validation and provide the variable \"subnets\" manually.
    The format should be 4 subnets for each AZ, and the name prefix should be \"fgt_login_\", \"fgt_internal_\", \"tgw_attachment_\", \"gwlbe_\".
    Here is an example:
    ```
      subnets = {
        fgt_login_2a = {
          cidr_block        = "10.0.0.0/24"
          availability_zone = "us-east-2a"
        },
        fgt_internal_2a = {
          cidr_block        = "10.0.1.0/24"
          availability_zone = "us-east-2a"
        },
        tgw_attachment_2a = {
          cidr_block        = "10.0.2.0/24"
          availability_zone = "us-east-2a"
        },
        gwlbe_2a = {
          cidr_block        = "10.0.3.0/24"
          availability_zone = "us-east-2a"
        },
        fgt_login_2b = {
          cidr_block        = "10.0.10.0/24"
          availability_zone = "us-east-2b"
        },
        fgt_internal_2b = {
          cidr_block        = "10.0.11.0/24"
          availability_zone = "us-east-2b"
        },
        tgw_attachment_2b = {
          cidr_block        = "10.0.12.0/24"
          availability_zone = "us-east-2b"
        },
        gwlbe_2b = {
          cidr_block        = "10.0.13.0/24"
          availability_zone = "us-east-2b"
        }
      }
    ```
    EOF
  }
}

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

## Auto scale group
variable "asgs" {
  description = <<-EOF
  Auto Scaling group map.
  Format:
  ```
    asgs = {
        \<ASG NAME\> = {
            \<Option\> = \<Option value\>
        }
    }
  ```
  Options:
    FortiGate instance template
    - template_name : (Optional|string) Instance template name.
    - fgt_version : (Required|string) FortiGate version for the FortiGate instances. If the whole version been provided, please make sure the version is exist. If part of version been provided, such as 7.2, will using the latest release of this version.
    - instance_type : (Optional|string) Instance type for the FortiGate instances. Default is c5.xlarge.
    - license_type : (Optional|string) License type for the FortiGate instances. Options: on_demand, byol. Default is on_demand.
    - fgt_hostname : (Optional|string) FortiGate instance hostname.
    - fgt_password : (Required|string) FortiGate instance login password. This is required for BYOL type of FortiGate instance since we need to upload the license to the instance by lambda function.
    - fgt_multi_vdom : (Optional|bool) Flag of FortiGate instance vdom type. `true` will be multi-vdom mode. `false` will be single-vdom mode. Default is `false`.
    - lic_folder_path : (Optional|string) Folder path of FortiGate license files.
    - lic_s3_name : (Optional|string) AWS S3 bucket name that contains FortiGate license files or token json file.
    - fortiflex_refresh_token : (Optional|string) Refresh token used for FortiFlex.
    - fortiflex_sn_list : (Optional|list) Serial number list from FortiFlex account that used to activate FortiGate instance.
    - fortiflex_configid_list : (Optional|list) Config ID list from FortiFlex account that used to activate FortiGate instance.
    - keypair_name : (Required|string) The keypair name for accessing the FortiGate instances.
    - enable_fgt_system_autoscale : (Optional|bool) If true, FotiGate system auto-scale will be set.
    - fgt_system_autoscale_psksecret : (Optional|string) FotiGate system auto-scale psksecret.
    - fgt_login_port_number : (Optional|string) The port number for the FortiGate instance. Should set this parameter if the port number for FortiGate instance login is not 443.
    - user_conf_content: (Optional|string) User configuration in CLI format that will applied to the FortiGate instance.
        The module do not cover the firewall policy generation. So, user should configure the firewall policy by this argumet.
        FortiGate instance port name format:
          1. For FortiGate port, the name should be 'port'+(device_index + 1). For example, if the device_index is 0, the the port name will be 'port1'.
          2. For interface tunnel with GENEVE protocol (used for connecting with GWLB target group), the name will be 'geneve-az<NUMBER>'. Check 'az_name_map' of the output of template, which is map of Geneve tunnel name to the AZ name that supported in Security VPC.
    - user_conf_file_path : (Optional|string) User configuration file path that will applied to FortiGate instance.
    - user_conf_s3 : (Optional|map(list(string))) User configuration files in AWS S3 that will applied to FortiGate instance.
        The key is the Bucket name, and the value is a list of key names in this Bucket.
    - intf_security_group : (Required|string) Security group map for FortiGate instance instances.
      Options:
        - login_port : (Required|string) Security group name for the login port of FortiGate instance.
        - internal_port : (Required|string) Security group name for the internal traffic port of FortiGate instance.
    Auto Scale Group
    - asg_max_size : (Required|number) Maximum size of the Auto Scaling Group.
    - asg_min_size : (Required|number) Minimum size of the Auto Scaling Group.
    - asg_desired_capacity : (Optional|number) Number of Amazon EC2 instances that should be running in the group.
    - create_dynamodb_table : (Optional|bool) If true, will create the DynamoDB table using dynamodb_table_name as the name. Default is false.
    - dynamodb_table_name : (Required|string) DynamoDB table name that used for tracking Auto Scale Group information, such as instance information and primary IP.
    - scale_policies : (Optional|map) Auto Scaling group scale policies.
      Key is policy name. Options for values of parameter scale_policies:
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
  asgs = {
    fgt_byol_asg = {
        template_name = "fgt_asg_template"
        fgt_version = "7.2"
        license_type = "byol"
        fgt_password = "ftnt"
        keypair_name = "keypair1"
        intf_security_group = {
          login_port    = "secgrp1"
          internal_port = "secgrp1"
        }
        asg_max_size = 3
        asg_min_size = 1
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
    }
  }
  ```
  EOF
  type        = any
}

variable "fgt_intf_mode" {
  description = <<-EOF
  FortiGate interface design. There are two options: 
    1-arm: only one port in FortiGate for both internet (including login/mgmt) and internal traffic (including Geneve tunnel); 
    2-arm: two ports in FortiGate, one for internet (including login/mgmt), another one for internal traffic (including Geneve tunnel);
  EOF
  default     = "2-arm"
  type        = string
  validation {
    condition     = contains(["1-arm", "2-arm"], var.fgt_intf_mode)
    error_message = "Value of variable fgt_intf_mode can not be identified. Available opitons: 1-arm, 2-arm."
  }
}

## Cloudwatch Alarm 
variable "cloudwatch_alarms" {
  description = <<-EOF
    Cloudwatch Alarm configuration.
    Format:
    ```
      cloudwatch_alarms = {
        \<Cloudwatch Alarm name\> = {
            \<Option name\> = \<Option value\>
        }
      }
    ```
    Cloudwatch Alarm options:
      - comparison_operator     : (Optional|string) The arithmetic operation to use when comparing the specified Statistic and Threshold. The specified Statistic value is used as the first operand. Either of the following is supported: GreaterThanOrEqualToThreshold, GreaterThanThreshold, LessThanThreshold, LessThanOrEqualToThreshold. Additionally, the values LessThanLowerOrGreaterThanUpperThreshold, LessThanLowerThreshold, and GreaterThanUpperThreshold are used only for alarms based on anomaly detection models.
      - evaluation_periods      : (Optional|number) The number of periods over which data is compared to the specified threshold.
      - metric_name             : (Optional|string) The name for the alarm's associated metric.
      - namespace               : (Optional|string) The namespace for the alarm's associated metric.
      - period                  : (Optional|number) The period in seconds over which the specified statistic is applied. Valid values are 10, 30, or any multiple of 60.
      - statistic               : (Optional|string) The statistic to apply to the alarm's associated metric. Either of the following is supported: SampleCount, Average, Sum, Minimum, Maximum.
      - threshold               : (Optional|list) The value against which the specified statistic is compared. This parameter is required for alarms based on static thresholds, but should not be used for alarms based on anomaly detection models.
      - dimensions              : (Optional|map) The dimensions for the alarm's associated metric.
      - alarm_description       : (Optional|string) The description for the alarm.
      - datapoints_to_alarm     : (Optional|number) The number of datapoints that must be breaching to trigger the alarm.
      - alarm_asg_policies      : (Optional|map) Information of auto-scale policies to execute when this alarm transitions into an ALARM state from any other state.
        Options for variable alarm_asg_policies:
        - policy_arn_list      : (Optional|list) The list of auto-scale policy ARNs.
        - policy_name_map      : (Optional|map) The map of Auto Scale Group name to the list of auto-scale policies under the ASG. The ASG must be handled by this template, and the template will grab the policy ARN based on the policy name.
    
    Example:
    ```
    cloudwatch_alarms = {
      cpu_above_80 = {
        comparison_operator = "GreaterThanOrEqualToThreshold"
        evaluation_periods  = 2
        metric_name         = "CPUUtilization"
        namespace           = "AWS/EC2"
        period              = 120
        statistic           = "Average"
        threshold           = 80
        dimensions = {
          AutoScalingGroupName = "fgt_asg_byol"
        }
        alarm_description = "This metric monitors average ec2 cpu utilization of Auto Scale group fgt_asg_byol."
        datapoints_to_alarm = 1
        alarm_asg_policies     = ["cpu_above_80"]
      }
    }
    ```
  EOF
  type        = any
  default     = {}
  validation {
    condition = var.cloudwatch_alarms == null ? true : alltrue([
      for k, v in var.cloudwatch_alarms : alltrue([
        for sk, sv in v : contains([
          "comparison_operator",
          "evaluation_periods",
          "metric_name",
          "namespace",
          "period",
          "statistic",
          "threshold",
          "dimensions",
          "alarm_description",
          "datapoints_to_alarm",
          "alarm_asg_policies"
        ], sk)
      ])
    ])
    error_message = "One or more argument(s) can not be identified, available options: comparison_operator, evaluation_periods, metric_name, namespace, period, statistic, threshold, dimensions, alarm_description, datapoints_to_alarm, alarm_asg_policies."
  }
}

## Gateway Load Balancer
variable "gwlb_name" {
  description = "Gateway Load Balancer name."
  type        = string
  default     = "gwlb-fgt"
}

variable "tgp_name" {
  description = "Target Group name."
  type        = string
  default     = "gwlb-tgp-fgt"
}

variable "enable_cross_zone_load_balancing" {
  description = "If true, cross-zone load balancing of the load balancer will be enabled."
  type        = bool
  default     = null
}

## Spoke VPC
variable "spk_vpc" {
  description = <<-EOF
    Spoke VPC configuration. VPC ID and Subnet IDs shold be provided. This module will create Gateway Load Balancer Endpoint under each subnet, and create VPC route tables to IGW with the subnet associated if argument `.
    Format:
    ```
        spk_vpc = {
            \<Spoke VPC name\> = {
                vpc_id = "\<VPC_ID\>"
                gwlbe_subnet_ids     = [
                  "SUBNET_ID"
                ]
                route_tables = {
                  \<Spoke VPC name\> = {
                    \<Option\> = \<Option value\>
                  }
                }
            }
        }
    ```
    Spoke VPC options:
        - vpc_id     : (Optional|string) Spoke VPC ID.
        - gwlbe_subnet_ids : (Optional|list) Subnet ID list. Note: Subnets that TGW will attach to should not already have a route table association.
        - route_tables     : (Optional|map) Route table configurations. Please check the detailed configuration requirement on module vpc_route_table. Note: if the target argument is the Gateway Load Balancer Endpoint created by the template, use `gwlbe_subnet_id` to specify the subnet ID of the target GWLBE.
    Example:
    ```
    spk_vpc = {
      "spk_vpc1" = {
        vpc_id = "vpc-123456789",
        gwlbe_subnet_ids = [
          "subnet-123456789",
          "subnet-123456789"
        ]
        route_tables = {
          igw_inbound = {
            routes = {
              az1 = {
                destination_cidr_block = "10.1.1.0/24"
                gwlbe_subnet_id        = "subnet-123456789"
              },
              az2 = {
                destination_cidr_block = "10.1.2.0/24"
                gwlbe_subnet_id        = "subnet-123456788"
              },
            },
            rt_association_gateways = ["igw-123456789"]
          },
          gwlbe_outbound = {
            routes = {
              az1 = {
                destination_cidr_block = "0.0.0.0/0"
                gateway_id        = "igw-123456789"
              }
            },
            rt_association_subnets = ["subnet-123456788", "subnet-123456789"]
          },
          pc_outbound_az1 = {
            routes = {
              az1 = {
                destination_cidr_block = "0.0.0.0/0"
                gwlbe_subnet_id        = "subnet-123456789"
              }
            },
            existing_rt = {
              id = "rtb-123456789"
            }
          },
          pc_outbound_az2 = {
            routes = {
              az1 = {
                destination_cidr_block = "0.0.0.0/0"
                gwlbe_subnet_id        = "subnet-123456788"
              }
            },
            existing_rt = {
              id = "rtb-123456788"
            }
          },
        }
      }
    }
    ```
  EOF
  type        = any
  default     = {}
  validation {
    condition = var.spk_vpc == null ? true : alltrue([
      for k, v in var.spk_vpc : alltrue([
        for sk, sv in v : contains([
          "vpc_id",
          "gwlbe_subnet_ids",
        "route_tables"], sk)
      ])
    ])
    error_message = "One or more argument(s) can not be identified, available options: vpc_id, gwlbe_subnet_ids, route_tables."
  }
}
